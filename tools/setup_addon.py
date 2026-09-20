"""Small, editable-settings front end for the existing companion installer.

Preparation never opens a module or touches a running server. Required NWNX
headers come from the owner's matching NWScript download, not a bundled version.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

from build_addon import settings as bridge_settings
from prepare_addon import prepare, HEADERS

ROOT = Path(__file__).resolve().parents[1]


def configuration(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    expected = {
        "world_id",
        "redis_prefix",
        "dashboard_port",
        "redis_port",
        "nwnx_headers",
        "output",
    }
    if set(value) != expected:
        raise ValueError("Use the six fields shown in addon/setup.json")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", value["world_id"]):
        raise ValueError(
            "world_id must start with a lowercase letter and use lowercase letters, digits or underscores (maximum 24)"
        )
    bridge_settings(value["world_id"], value["redis_prefix"])
    for key in ("dashboard_port", "redis_port"):
        if type(value[key]) is not int or not 1024 <= value[key] <= 65535:
            raise ValueError(key + " must be a port from 1024 to 65535")
    if value["dashboard_port"] == value["redis_port"]:
        raise ValueError("Dashboard and Redis need different ports")
    for key in ("nwnx_headers", "output"):
        path = Path(value[key]).expanduser()
        value[key] = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    return value


def required_headers(directory):
    """Collect the transitive NWNX include closure, preserving exact source bytes."""
    result = {}

    def visit(name):
        if name in result:
            return
        if not re.fullmatch(r"nwnx_[a-z0-9_]+", name):
            raise ValueError("Invalid NWNX include name: " + name)
        path = directory / (name + ".nss")
        if not path.is_file():
            raise ValueError(
                "Missing NWNX script: "
                + str(path)
                + ". Extract the NWScript.zip matching your installed NWNX build here."
            )
        raw = path.read_bytes()
        result[name] = raw
        for dependency in re.findall(
            r'^\s*#include\s+"([^"]+)"', raw.decode("utf-8-sig"), re.M
        ):
            if dependency.startswith("nwnx_"):
                visit(dependency)

    for name in HEADERS:
        visit("nwnx_" + name)
    return result


def write_erf(path, files):
    """Aurora ERF V1.0: source scripts and blueprints; no module/area replacement."""
    types = {".nss": 2009, ".ncs": 2010, ".utc": 2027, ".utm": 2051}
    entries = [(p.stem, types[p.suffix], p.read_bytes()) for p in sorted(files)]
    if any(len(name) > 16 for name, _, _ in entries):
        raise ValueError("Aurora resource names must be at most 16 characters")
    if len({(name, kind) for name, kind, _ in entries}) != len(entries):
        raise ValueError("Duplicate resources in import")
    header = bytearray(160)
    header[:8] = b"ERF V1.0"
    key_offset, resource_offset = 160, 160 + 24 * len(entries)
    struct.pack_into(
        "<9I",
        header,
        8,
        0,
        0,
        len(entries),
        160,
        key_offset,
        resource_offset,
        0,
        0,
        0xFFFFFFFF,
    )
    keys, offsets, data = bytearray(), bytearray(), bytearray()
    base = resource_offset + 8 * len(entries)
    for index, (name, kind, raw) in enumerate(entries):
        keys.extend(struct.pack("<16sIHH", name.encode("ascii"), index, kind, 0))
        offsets.extend(struct.pack("<II", base + len(data), len(raw)))
        data.extend(raw)
    path.write_bytes(header + keys + offsets + data)


def prepare_import(config):
    # Resolve every dependency before creating output, so a missing header leaves no partial bundle.
    headers = required_headers(config["nwnx_headers"])
    output = config["output"]
    manifest = prepare(
        output, config["world_id"], config["redis_prefix"], source_only=True
    )
    scripts = output / "scripts"
    for name, raw in headers.items():
        (scripts / (name + ".nss")).write_bytes(raw)
    templates = ROOT / "addon/templates"
    for name in ["rw_userload.nss", "rw_userchat.nss"]:
        (scripts / name).write_bytes((templates / name).read_bytes())
    write_erf(
        output / "RoleWeaver-Import.erf",
        [
            *scripts.glob("*.nss"),
            *(output / "optional-assets").glob("*.utc"),
            *(output / "optional-assets").glob("*.utm"),
        ],
    )
    (output / "INSTALL.md").write_text(
        (ROOT / "addon/AURORA.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (output / "INTEGRATION.md").write_bytes(
        (ROOT / "addon/INTEGRATION.md").read_bytes()
    )
    manifest["nwnx_headers"] = sorted(headers)
    manifest["files"] = {
        p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Ready:", output / "RoleWeaver-Import.erf")
    print("Next: open", output / "INSTALL.md")
    print("Your module and running servers have not been changed.")
    return manifest


def run(action, config):
    if action == "prepare":
        return prepare_import(config)
    if sys.platform != "linux":
        raise ValueError("Run companion commands inside Ubuntu/Linux")
    unit = "roleweaver-" + config["world_id"] + ".service"
    if action in ("restart", "status"):
        subprocess.run(["systemctl", "--user", action, unit], check=True)
        return
    args = [
        sys.executable,
        str(ROOT / "tools/install_companion.py"),
        action,
        "--world-id",
        config["world_id"],
        "--port",
        str(config["dashboard_port"]),
        "--redis-port",
        str(config["redis_port"]),
        "--redis-prefix",
        config["redis_prefix"],
    ]
    subprocess.run(args, check=True)
    if action == "install":
        # Existing installer refuses to overwrite an active installation. Never stop it implicitly.
        unit_file = Path.home() / ".local/share/roleweaver" / config["world_id"] / unit
        subprocess.run(["systemctl", "--user", "link", str(unit_file)], check=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", unit], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["check", "prepare", "install", "restart", "status"]
    )
    parser.add_argument("--config", type=Path, default=ROOT / "addon/setup.json")
    args = parser.parse_args()
    try:
        run(args.action, configuration(args.config))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print("Setup stopped:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
