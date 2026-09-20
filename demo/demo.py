"""Editable, isolated Linux demo: prepare a world, run it, and preserve tester data.

No existing world, password file, systemd service or provider key is imported.
The foreground runner owns only the two child processes it launches.
"""

import argparse
import getpass
import ipaddress
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from roleweaver.store import Store, DEFAULT_NPC
from roleweaver import actions, conversation, safeguards, merchants
from roleweaver.lore_documents import validate_documents
from build_addon import build
from demo.investigation.runtime import build_investigation


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    Path(path).chmod(0o600)


def content(path):
    value = read_json(path)
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("npcs"), list)
        or not 1 <= len(value["npcs"]) <= 20
    ):
        raise ValueError("content.json needs 1–20 NPCs")
    for key in ("area_tag", "blueprint"):
        if not isinstance(value.get(key), str) or not re.fullmatch(
            r"[A-Za-z0-9_]{1,32}", value[key]
        ):
            raise ValueError("Invalid " + key)
    for key, validator in (
        ("conversation", conversation.settings),
        ("safeguards", safeguards.settings),
        ("merchant_configs", merchants.configs),
    ):
        if key in value:
            value[key] = validator(value[key])
    ids = set()
    for npc in value["npcs"]:
        actions.identifier(npc["id"])
        if npc["id"] in ids:
            raise ValueError("Duplicate NPC ID")
        ids.add(npc["id"])
        for key in ("name", "role", "personality", "voice", "lore", "boundaries"):
            if (
                not isinstance(npc.get(key), str)
                or not npc[key].strip()
                or len(npc[key]) > 6000
            ):
                raise ValueError("Invalid NPC " + key)
        if len(npc["name"]) > 80 or any(ord(c) < 32 for c in npc["name"]):
            raise ValueError("Invalid display name")
        # Names are embedded in a native source string; keep this demo input unambiguous.
        if any(c in npc["name"] for c in ('"', "\\")):
            raise ValueError("NPC display names cannot contain quotes or backslashes")
        for key in ("x", "y", "z", "facing"):
            npc.setdefault(key, 0.0)
            if (
                type(npc.get(key)) not in (int, float)
                or not math.isfinite(npc[key])
                or not (-100000 if key == "z" else 0) <= npc[key] <= 100000
            ):
                raise ValueError("Invalid NPC coordinate")
        if type(npc.get("shop")) is not bool:
            raise ValueError("shop must be true or false")
    value["world_documents"] = validate_documents(value.get("world_documents", []))
    return value


def seed_script(value):
    """World-owned test characters are recreated on module load, then bound to profiles."""
    rows = [
        '#include "rw_inc"',
        "void main() {",
        "    object m=GetModule();",
        '    SetLocalInt(m,"rw_allow_dm_spawn",TRUE);',
        '    SetLocalInt(m,"rw_allow_persistent_spawn",TRUE);',
        f'    object area=GetObjectByTag("{value["area_tag"]}");',
        '    if(!GetIsObjectValid(area)) { WriteTimestampedLogEntry("RW_DEMO: area tag not found"); return; }',
    ]
    for i, n in enumerate(value["npcs"]):
        if not n.get("spawn", True):
            continue
        creature = {
            k: int(n[k])
            for k in ("appearance", "race", "gender", "npc_class", "level")
            if k in n
        }
        location = f'Location(area,Vector({n["x"]:.3f},{n["y"]:.3f},{n.get("z", 0.0):.3f}),{n.get("facing", 0.0):.3f})'
        if len(creature) == 5:
            payload = json.dumps(creature, separators=(",", ":")).replace('"', '\\"')
            create = f'RWCreateCreature(JsonParse("{payload}"),{location})'
        else:
            create = (
                f'CreateObject(OBJECT_TYPE_CREATURE,"{value["blueprint"]}",{location})'
            )
        rows += [
            f'    object n{i}=RWFind("{n["id"]}"); if(!GetIsObjectValid(n{i})) n{i}={create};',
            f'    if(GetIsObjectValid(n{i})) {{ SetName(n{i},"{n["name"]}"); SetLocalString(n{i},"rw_profile","{n["id"]}"); ExecuteScript("rw_bind",n{i}); RWMode(n{i},"auto"); }}',
        ]
    return "\n".join(rows + ["}", ""])


def seed_database(path, value, world="rw_demo"):
    """Upsert supplied profiles/lore; never erase conversations or removed profiles."""
    path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(path)
    try:
        policies = {}
        for npc in value["npcs"]:
            profile = dict(
                DEFAULT_NPC,
                **{k: v for k, v in npc.items() if k in DEFAULT_NPC and k != "mode"},
                mode="auto",
            )
            store.save(profile)
            policies[npc["id"]] = dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                gestures=["greet"],
                shop=npc["shop"],
            )
        for doc in value["world_documents"]:
            store.save_world_document(doc)
        for doc in value.get("access_lore", []):
            store.save_access_lore(doc)
        row = store.db.execute(
            "SELECT value FROM backup_settings WHERE key='controlled_actions'"
        ).fetchone()
        config = actions.settings(json.loads(row[0]) if row else None)
        config["npcs"].update(policies)
        supplied = actions.settings(value.get("controlled_actions"))
        config["npcs"].update(supplied["npcs"])
        for key, destination in supplied["destinations"].items():
            config["destinations"][key] = dict(destination, world=world)
        with store.db:
            for key, validator in (
                ("conversation", conversation.settings),
                ("safeguards", safeguards.settings),
                ("merchant_configs", merchants.configs),
            ):
                if key in value:
                    store.db.execute(
                        "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                        (key, json.dumps(validator(value[key]))),
                    )
            store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                ("controlled_actions", json.dumps(config)),
            )
            store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                ("startup_auto", "true"),
            )
    finally:
        store.db.close()


def dependencies(native, compiler):
    required = [native / "runtime/bin/linux-x86/nwserver-linux", compiler]
    required += [
        native / "plugins" / ("NWNX_" + name + ".so")
        for name in ("Core", "Chat", "Events", "Redis", "Creature", "Player")
    ]
    required += [native / "nwscripts/nwnx_chat.nss"]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise ValueError("Missing dependencies:\n" + "\n".join(missing))
    for executable in required[:2]:
        if not os.access(executable, os.X_OK):
            raise ValueError("Not executable: " + str(executable))


@contextlib.contextmanager
def instance_lock(runtime):
    """An OS lock prevents rebuild/import while this instance is running."""
    import fcntl

    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime / "instance.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                "Demo is running. Stop it with Ctrl+C before making this change."
            ) from None
        yield


def compile_world(runtime, settings):
    value = content(settings["content"])
    native, compiler = Path(settings["native"]), Path(settings["compiler"])
    dependencies(native, compiler)
    # The generic builder currently locates the compiler here. Never replace an existing link/file.
    link = ROOT / "tools/nwnsc"
    if link.exists() or link.is_symlink():
        if link.resolve() != compiler.resolve():
            raise ValueError(
                "tools/nwnsc points to a different compiler; choose it or correct the link yourself"
            )
    else:
        link.symlink_to(compiler)
    bundle = runtime / "builds" / str(time.time_ns())
    bundle.parent.mkdir(exist_ok=True)
    if value.get("scenario") == "investigation":
        build_investigation(
            Path(settings["module"]),
            bundle,
            native,
            compiler,
            settings["id"],
            settings["prefix"],
            seed_script(value),
        )
    else:
        build(
            Path(settings["module"]),
            bundle,
            native,
            settings["id"],
            settings["prefix"],
            "world",
            "module",
        )
        (bundle / "bridge/rw_demoseed.nss").write_text(seed_script(value))
        load = bundle / "bridge/rw_load.nss"
        load.write_text(
            load.read_text().replace(
                '    ExecuteScript("rw_init", GetModule());',
                '    ExecuteScript("rw_init", GetModule());\n    ExecuteScript("rw_demoseed", GetModule());',
            )
        )
        for name in ("rw_load", "rw_demoseed"):
            subprocess.run(
                [
                    str(compiler),
                    "-n",
                    str(native / "runtime"),
                    "-i",
                    str(native / "nwscripts") + ";" + str(bundle / "bridge"),
                    str(bundle / "bridge" / (name + ".nss")),
                ],
                check=True,
                timeout=30,
                capture_output=True,
            )
            shutil.move(
                str(bundle / "bridge" / (name + ".ncs")),
                bundle / "compiled" / (name + ".ncs"),
            )
    # Both compilation steps succeed before touching the instance's active game files.
    userdata = runtime / "userdata"
    if (userdata / "modules").exists():
        saved = runtime / "previous-builds" / str(time.time_ns())
        shutil.copytree(userdata / "modules", saved / "modules")
        shutil.copytree(userdata / "override", saved / "override")
    (userdata / "modules").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        bundle / "module" / Path(settings["module"]).name,
        userdata / "modules/YourWorld_Fixed.mod",
    )
    shutil.copytree(bundle / "compiled", userdata / "override", dirs_exist_ok=True)
    write_json(
        runtime / "last-build.json",
        {
            "source_module": settings["module"],
            "sha256": hashlib.sha256(Path(settings["module"]).read_bytes()).hexdigest(),
            "content": settings["content"],
            "bundle": str(bundle),
        },
    )
    return value


def prepare(runtime, args):
    if (runtime / "settings.json").exists():
        raise ValueError(
            "Already prepared. Use rebuild or a new --instance name; saved data is not overwritten."
        )
    if args.native is None or args.compiler is None:
        raise ValueError("setup needs --native and --compiler paths")
    if args.game_port == args.web_port or not all(
        1024 <= p <= 65535 for p in (args.game_port, args.web_port, args.redis_port)
    ):
        raise ValueError("Choose distinct game/dashboard ports between 1024 and 65535")
    settings = dict(
        id=args.instance,
        prefix="roleweaver:" + args.instance,
        native=str(args.native.resolve()),
        compiler=str(args.compiler.resolve()),
        module=str(args.module.resolve()),
        content=str(args.content.resolve()),
        game_port=args.game_port,
        web_port=args.web_port,
        redis_port=args.redis_port,
        dm_password=secrets.token_urlsafe(12),
    )
    if args.guardrails:
        from roleweaver.guardrails import ValidationEngine

        engine = ValidationEngine(True)
        if engine.error:
            raise ValueError(
                "Install requirements-guardrails.txt into this Python environment first"
            )
    value = compile_world(runtime, settings)
    seed_database(runtime / "data/roleweaver.sqlite3", value, settings["id"])
    config = read_json(ROOT / "config.example.json")
    config.update(
        world_id=settings["id"],
        redis_prefix=settings["prefix"],
        web_port=args.web_port,
        redis_port=args.redis_port,
        world_name="Role Weaver editable demo",
        allow_dm_spawn=True,
        allow_persistent_spawn=True,
        guardrails_ai=args.guardrails,
    )
    write_json(runtime / "config.json", config)
    write_json(runtime / "settings.json", settings)
    print("Prepared. Run: python demo/demo.py start --instance " + args.instance)


def check_validation_environment(runtime):
    """Fail before starting NWN when enabled validation cannot run in this Python."""
    config = json.loads((runtime / "config.json").read_text(encoding="utf-8"))
    if config.get("guardrails_ai", False):
        from roleweaver.guardrails import ValidationEngine

        if not ValidationEngine(True).status()["active"]:
            raise ValueError(
                "Guardrails AI is enabled but unavailable in this Python: "
                + sys.executable
                + ". From the package folder, run .venv/bin/python -m pip install "
                "-r requirements-guardrails.txt, then .venv/bin/python demo/demo.py start "
                "(keep your --instance option if used). No demo processes were started."
            )


def check_ports(settings):
    """Match the dashboard's bind behavior, including recently closed connections."""
    for port, kind in (
        (settings["game_port"], socket.SOCK_DGRAM),
        (settings["web_port"], socket.SOCK_STREAM),
    ):
        with socket.socket(socket.AF_INET, kind) as sock:
            host = "0.0.0.0"
            if kind == socket.SOCK_STREAM:
                host = "127.0.0.1"
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError as error:
                label = "dashboard TCP" if kind == socket.SOCK_STREAM else "game UDP"
                raise ValueError(
                    f"Cannot use demo {label} port {port}: {error}. "
                    "Check whether another instance is running."
                ) from error


def host_ipv4_addresses():
    """List assigned addresses without contacting an external network service."""
    try:
        result = subprocess.run(
            ["ip", "-j", "-4", "address", "show", "up"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        addresses = set()
        for interface in json.loads(result.stdout):
            for entry in interface.get("addr_info", []):
                if entry.get("scope") != "global":
                    continue
                address = ipaddress.IPv4Address(entry["local"])
                if (
                    not address.is_loopback
                    and not address.is_link_local
                    and not address.is_unspecified
                ):
                    addresses.add(str(address))
        return sorted(addresses)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return []


def connection_instructions(settings, addresses, username):
    game, web = settings["game_port"], settings["web_port"]
    lines = [
        "Starting the demo. Wait for the module and dashboard to finish loading.",
        "NWN Direct Connect:",
        f"  On this Ubuntu computer: 127.0.0.1:{game}",
    ]
    if addresses:
        lines += [f"  From another computer: {address}:{game}" for address in addresses]
        lines.append(
            "  Use the Ubuntu/VM address reachable from your client; VPN/container addresses may not be reachable."
        )
    else:
        lines.append(
            f"  From another computer: UBUNTU-IP:{game} (run hostname -I in Ubuntu to find its IP)"
        )
    lines += [
        "Dashboard:",
        f"  In Ubuntu: http://127.0.0.1:{web}",
        "  From Windows/another computer, run this SSH tunnel there and leave it open:",
        f"    ssh -N -L {web}:127.0.0.1:{web} {username}@{addresses[0] if len(addresses) == 1 else 'UBUNTU-IP'}",
        f"  Then open http://127.0.0.1:{web} on that computer.",
        "  SSH must be enabled in Ubuntu. The dashboard listens only on localhost.",
    ]
    return "\n".join(lines)


def launch(runtime, settings):
    check_validation_environment(runtime)
    dependencies(Path(settings["native"]), Path(settings["compiler"]))
    check_ports(settings)
    with socket.create_connection(
        ("127.0.0.1", settings["redis_port"]), timeout=3
    ) as sock:
        sock.sendall(b"*1\r\n$4\r\nPING\r\n")
        if not sock.recv(128).startswith(b"+PONG"):
            raise ValueError("Redis did not answer PING")
    native = Path(settings["native"])
    binary = native / "runtime/bin/linux-x86/nwserver-linux"
    env = dict(
        os.environ,
        LD_PRELOAD=str(native / "plugins/NWNX_Core.so"),
        LD_LIBRARY_PATH=str(native / "plugins"),
        NWNX_CORE_LOAD_PATH=str(native / "plugins"),
        NWNX_CORE_SKIP_ALL="1",
        NWNX_REDIS_HOST="127.0.0.1",
        NWNX_REDIS_PORT=str(settings["redis_port"]),
        NWNX_CORE_LOG_LEVEL="4",
        NWNX_CORE_LOG_FILE_PATH=str(runtime / "nwnx.log"),
    )
    for name in ("PLAYER", "CREATURE", "CHAT", "EVENTS", "REDIS"):
        env["NWNX_" + name + "_SKIP"] = "n"
    game = [
        str(binary),
        "-userdirectory",
        str(runtime / "userdata"),
        "-module",
        "YourWorld_Fixed",
        "-port",
        str(settings["game_port"]),
        "-publicserver",
        "0",
        "-servername",
        "Role Weaver Alpha Demo",
        "-servervault",
        "0",
        "-maxclients",
        "8",
        "-reloadwhenempty",
        "0",
        "-dmpassword",
        settings["dm_password"],
        "-interactive",
    ]
    children = []
    try:
        with (
            (runtime / "game.log").open("ab") as game_log,
            (runtime / "dashboard.log").open("ab") as app_log,
        ):
            children.append(
                subprocess.Popen(
                    game,
                    cwd=binary.parent,
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=game_log,
                    stderr=subprocess.STDOUT,
                )
            )
            children.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "roleweaver.web",
                        "--config",
                        str(runtime / "config.json"),
                    ],
                    cwd=ROOT,
                    stdout=app_log,
                    stderr=subprocess.STDOUT,
                )
            )
            print(
                connection_instructions(
                    settings, host_ipv4_addresses(), getpass.getuser()
                ),
                flush=True,
            )
            print("DM password is in " + str(runtime / "settings.json"), flush=True)
            print(
                "Keep this terminal open. Ctrl+C stops this demo only. Logs are in "
                + str(runtime),
                flush=True,
            )
            while all(p.poll() is None for p in children):
                time.sleep(0.5)
            raise RuntimeError(
                "A demo process exited; inspect game.log and dashboard.log"
            )
    except KeyboardInterrupt:
        print("Stopping demo...")
    finally:
        for p in children:
            if p.poll() is None:
                p.terminate()
        for p in children:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("setup", "start", "rebuild", "apply-content", "check-content"),
    )
    parser.add_argument("--instance", default="rw_demo")
    parser.add_argument("--native", type=Path)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument(
        "--module", type=Path, default=ROOT / "demo/world/YourWorld_Fixed.mod"
    )
    parser.add_argument("--content", type=Path, default=ROOT / "demo/content.json")
    parser.add_argument("--game-port", type=int, default=5125)
    parser.add_argument("--web-port", type=int, default=8745)
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument(
        "--guardrails",
        action="store_true",
        help="Enable installed optional Guardrails AI validators",
    )
    args = parser.parse_args()
    actions.identifier(args.instance)
    if args.action == "check-content":
        content(args.content)
        print("Demo content is valid")
        return
    if sys.platform != "linux":
        raise ValueError("Run the demo server inside Linux (Ubuntu 24.04 recommended)")
    os.umask(0o077)
    runtime = ROOT / ".demo" / args.instance
    with instance_lock(runtime):
        if args.action == "setup":
            prepare(runtime, args)
            return
        settings = read_json(runtime / "settings.json")
        if args.action == "start":
            signal.signal(
                signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt())
            )
            launch(runtime, settings)
        elif args.action == "rebuild":
            compile_world(runtime, settings)
            print(
                "Rebuilt game files. Existing profiles, lore, keys, memories and campaign data were preserved."
            )
        else:
            value = content(settings["content"])
            saved = runtime / "content-backups" / (str(time.time_ns()) + ".sqlite3")
            saved.parent.mkdir(exist_ok=True)
            with (
                sqlite3.connect(runtime / "data/roleweaver.sqlite3") as db,
                sqlite3.connect(saved) as out,
            ):
                db.backup(out)
            seed_database(runtime / "data/roleweaver.sqlite3", value, settings["id"])
            print(
                "Applied profile/lore templates. Saved database backup: " + str(saved)
            )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print("Demo stopped: " + str(exc), file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(
                (
                    (exc.stdout or b"").decode(errors="replace")
                    if isinstance(exc.stdout, bytes)
                    else exc.stdout or ""
                ),
                file=sys.stderr,
            )
        sys.exit(1)
