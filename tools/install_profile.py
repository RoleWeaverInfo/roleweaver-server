"""Non-secret installation profiles, read-only discovery and prerequisite checks.

Profiles live outside extracted packages so a new download can resume setup.
Discovery reads only selected process arguments/environment keys, never launchers
or credentials. Presence checks cannot establish native binary compatibility.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from roleweaver.db_recovery import atomic_json
from setup_addon import required_headers

PLUGINS = (
    "Core",
    "Chat",
    "Events",
    "Redis",
    "Creature",
    "Player",
    "Item",
    "Dialog",
    "Util",
)
FEATURES = (
    "companions",
    "dm_spawn",
    "persistent_spawn",
    "merchants",
    "translation",
    "guardrails",
)
PATHS = ("runtime", "server_home", "module", "plugins", "headers", "compiler")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", value):
        raise ValueError(
            "World ID: use 1–24 lowercase letters, digits or underscores; start with a letter"
        )
    return value


def profile_directory():
    return Path.home() / ".config/roleweaver/installations"


def installation(world):
    return Path.home() / ".local/share/roleweaver" / identifier(world)


def profile_path(world):
    return profile_directory() / (identifier(world) + ".json")


def validate(p):
    expected = {
        "version",
        "world_id",
        "redis_prefix",
        "redis_port",
        "dashboard_port",
        "paths",
        "features",
        "resources",
        "progress",
    }
    if (
        not isinstance(p, dict)
        or set(p) != expected
        or type(p["version"]) is not int
        or p["version"] != 1
    ):
        raise ValueError(
            "Unsupported installation profile; run configure to create one"
        )
    identifier(p["world_id"])
    if not isinstance(p["redis_prefix"], str) or not re.fullmatch(
        r"[a-zA-Z0-9_:-]{1,80}", p["redis_prefix"]
    ):
        raise ValueError("Invalid Redis namespace")
    for key in ("redis_port", "dashboard_port"):
        if type(p[key]) is not int or not 1024 <= p[key] <= 65535:
            raise ValueError("Ports must be integers from 1024 to 65535")
    if p["redis_port"] == p["dashboard_port"]:
        raise ValueError("Dashboard and Redis need different ports")
    if not isinstance(p["paths"], dict) or set(p["paths"]) != set(PATHS):
        raise ValueError("Invalid server paths")
    if not isinstance(p["resources"], list) or len(p["resources"]) > 32:
        raise ValueError("Choose at most 32 loose resource folders")
    for value in [*p["paths"].values(), *p["resources"]]:
        if (
            not isinstance(value, str)
            or any(c in value for c in '\n\r\0"%\\')
            or (value and not Path(value).is_absolute())
        ):
            raise ValueError(
                "Use absolute Linux paths without control characters, quotes, percent or backslashes"
            )
    if (
        not isinstance(p["features"], dict)
        or set(p["features"]) != set(FEATURES)
        or any(type(v) is not bool for v in p["features"].values())
    ):
        raise ValueError("Invalid feature choices")
    if p["features"]["persistent_spawn"] and not p["features"]["dm_spawn"]:
        raise ValueError("Persistent DM spawning also needs DM spawning")
    if not isinstance(p["progress"], dict) or set(p["progress"]) - {
        "bundle",
        "bundle_signature",
        "installed",
        "verified",
    }:
        raise ValueError("Invalid setup progress")
    if any(not isinstance(v, str) for v in p["progress"].values()):
        raise ValueError("Invalid setup progress values")
    return p


def save(p):
    validate(p)
    dest = profile_path(p["world_id"])
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_json(dest, p)
    dest.chmod(0o600)


def load(world):
    p = validate(json.loads(profile_path(world).read_text(encoding="utf-8")))
    if p["world_id"] != world:
        raise ValueError("Profile filename and world ID disagree")
    return p


def installed_settings(p):
    path = installation(p["world_id"]) / "config.json"
    if not path.exists():
        return None
    config = json.loads(path.read_text())
    if (
        config.get("world_id"),
        config.get("redis_prefix"),
        config.get("redis_port"),
        config.get("web_port"),
    ) != (p["world_id"], p["redis_prefix"], p["redis_port"], p["dashboard_port"]):
        raise ValueError(
            "Saved choices do not match the installed world. Reconfigure using its existing identity and ports; upgrades cannot migrate them."
        )
    return config


def discover(proc=Path("/proc")):
    """Return candidate installations, not a claim that their plugins are loaded."""
    result = []
    if proc.is_dir():
        for item in proc.iterdir():
            try:
                if (
                    not item.name.isdigit()
                    or (item / "exe").resolve().name != "nwserver-linux"
                ):
                    continue
                args = (item / "cmdline").read_bytes().decode().rstrip("\0").split("\0")
                env = dict(
                    v.split("=", 1)
                    for v in (item / "environ").read_bytes().decode().split("\0")
                    if "=" in v
                )

                def argument(name, default=""):
                    return (
                        args[args.index(name) + 1]
                        if name in args and args.index(name) + 1 < len(args)
                        else default
                    )

                server = argument(
                    "-userdirectory",
                    str(Path.home() / ".local/share/Neverwinter Nights"),
                )
                module = argument("-module")
                result.append(
                    dict(
                        runtime=str((item / "exe").resolve().parents[2]),
                        server_home=server,
                        module=(
                            str(
                                Path(server)
                                / "modules"
                                / (module.removesuffix(".mod") + ".mod")
                            )
                            if module
                            else ""
                        ),
                        plugins=env.get("NWNX_CORE_LOAD_PATH", ""),
                    )
                )
            except (OSError, UnicodeError, ValueError):
                continue
    return result


def defaults():
    h = Path.home()

    def first(paths):
        return str(next((p for p in paths if p.exists()), paths[0]))

    return dict(
        runtime=first([h / "nwserver", h / "nwn/server"]),
        server_home=str(h / "nwn-world"),
        module="",
        plugins=first(
            [h / "nwnx/plugins", h / "unified/Binaries", h / "nwnxee/Binaries"]
        ),
        headers=first([h / "nwnx/nwscripts", h / "unified/NWScript"]),
        compiler=shutil.which("nwnsc")
        or (str(h / "bin/nwnsc") if (h / "bin/nwnsc").exists() else ""),
    )


def checks(p, network=True):
    """Return actionable rows; never start services, install packages or contact an LLM."""
    validate(p)
    rows = []

    def row(name, ok, detail, warning=False):
        rows.append(
            dict(
                name=name,
                status="ok" if ok else "review" if warning else "fix",
                detail=detail,
            )
        )

    row(
        "Linux/Python",
        sys.platform == "linux" and sys.version_info >= (3, 10),
        "Requires Linux and Python 3.10 or newer.",
    )
    row(
        "User services",
        bool(shutil.which("systemctl")),
        "Requires systemd user services; run setup as the server owner, without sudo.",
    )
    paths = {k: Path(v) if v else None for k, v in p["paths"].items()}
    runtime = paths["runtime"]
    row(
        "NWN runtime",
        bool(
            runtime
            and (runtime / "bin/linux-x86/nwserver-linux").is_file()
            and list((runtime / "data").glob("*.key"))
            and list((runtime / "data").glob("*.bif"))
        ),
        "Select the NWN root containing bin/linux-x86 and data/*.key, data/*.bif.",
    )
    row(
        "Server home",
        bool(paths["server_home"] and paths["server_home"].is_dir()),
        "Choose this world's userdirectory, containing modules/ and its other content.",
    )
    row(
        "Module",
        bool(
            paths["module"]
            and paths["module"].is_file()
            and paths["module"].suffix.lower() == ".mod"
        ),
        "Select the actual .mod file; setup only reads it for integration review.",
    )
    missing = [
        n
        for n in PLUGINS
        if not paths["plugins"] or not (paths["plugins"] / f"NWNX_{n}.so").is_file()
    ]
    row(
        "NWNX plugins",
        not missing,
        (
            "Missing: " + ", ".join(missing)
            if missing
            else "Required plugin files are present; loaded versions are checked after connection."
        ),
    )
    try:
        required_headers(paths["headers"] or Path("/nonexistent-headers"))
        row(
            "NWNX includes",
            True,
            "Required include dependencies found. Use headers matching your installed NWNX build.",
        )
    except (ValueError, OSError) as exc:
        row("NWNX includes", False, str(exc))
    compiler = paths["compiler"]
    row(
        "Compiler",
        bool(compiler and compiler.is_file() and os.access(compiler, os.X_OK)),
        "No executable nwnsc selected: import and compile in Aurora, or select an installed compiler.",
        warning=not compiler,
    )
    row(
        "Custom integration",
        False,
        "Review existing load/chat hooks and resource precedence. HAK archives/custom frameworks are not automatically analysed.",
        warning=True,
    )
    for path in p["resources"]:
        row("Loose resources", Path(path).is_dir(), path)
    try:
        installed = installed_settings(p)
    except (ValueError, OSError) as exc:
        installed = None
        row("Installed identity", False, str(exc))
    if network:
        if shutil.which("systemctl"):
            bus = subprocess.run(
                ["systemctl", "--user", "show-environment"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            row(
                "User service connection",
                bus.returncode == 0,
                "The systemd user manager must be available. Sign in as the server owner; do not run setup through sudo.",
            )
        try:
            with socket.create_connection(
                ("127.0.0.1", p["redis_port"]), timeout=2
            ) as sock:
                sock.sendall(b"*1\r\n$4\r\nPING\r\n")
                ok = sock.recv(128).startswith(b"+PONG")
            row(
                "Redis",
                ok,
                "Uses local Redis without authentication. Preserve shared Redis configuration; authentication/TLS/remote endpoints need separate integration work.",
            )
        except OSError:
            row(
                "Redis",
                False,
                f"No Redis on 127.0.0.1:{p['redis_port']}. On a fresh Ubuntu host: sudo apt install redis-server. Do not reconfigure a shared instance blindly.",
            )
        if not installed:
            try:
                with socket.socket() as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("127.0.0.1", p["dashboard_port"]))
                row("Dashboard port", True, "Loopback port is available.")
            except OSError:
                row(
                    "Dashboard port",
                    False,
                    "Port is occupied; choose another dashboard port.",
                )
    return rows


def signature(p):
    """Invalidate a prepared bundle when choices or shipped bridge resources change."""
    digest = hashlib.sha256(
        json.dumps(
            {k: v for k, v in p.items() if k != "progress"}, sort_keys=True
        ).encode()
    )
    for folder in (ROOT / "bridge", ROOT / "assets", ROOT / "addon/templates"):
        for path in sorted(folder.glob("*")):
            if path.is_file():
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
    for name in (
        "tools/install_bundle.py",
        "tools/setup_addon.py",
        "tools/prepare_addon.py",
        "addon/AURORA.md",
        "addon/INTEGRATION.md",
    ):
        path = ROOT / name
        if path.is_file():
            digest.update(path.read_bytes())
    for folder in p["resources"]:
        for path in sorted(Path(folder).rglob("*")):
            if path.is_file() and path.suffix.lower() in (".nss", ".ncs"):
                digest.update(str(path).encode())
                digest.update(path.read_bytes())
    headers = Path(p["paths"]["headers"])
    for name, raw in sorted(required_headers(headers).items()):
        digest.update(name.encode())
        digest.update(raw)
    module = Path(p["paths"]["module"])
    if module.is_file():
        digest.update(module.read_bytes())
    return digest.hexdigest()
