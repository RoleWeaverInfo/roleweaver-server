#!/usr/bin/env python3
"""Install the companion only; never edits NWN modules or starts NWN."""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent.parent


def identifier(value):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", value):
        raise ValueError(
            "World ID must start with a lowercase letter and contain at most 32 lowercase letters, digits or underscores"
        )
    return value


def check(args):
    errors = []
    if sys.platform != "linux":
        errors.append("Run this installer inside Linux")
    if sys.version_info < (3, 10):
        errors.append("Python 3.10 or newer is required")
    if not shutil.which("systemctl"):
        errors.append("systemctl is required for the user service")
    try:
        with socket.create_connection(("127.0.0.1", args.redis_port), timeout=2) as s:
            s.sendall(b"*1\r\n$4\r\nPING\r\n")
            if not s.recv(128).startswith(b"+PONG"):
                errors.append(
                    "Local Redis did not accept PING (this companion requires unauthenticated loopback Redis)"
                )
    except OSError:
        errors.append("Redis is not reachable on 127.0.0.1:" + str(args.redis_port))
    if args.native:
        native = args.native.resolve()
        for name in ("Core", "Chat", "Events", "Redis", "Creature", "Player"):
            if not (native / "plugins" / ("NWNX_" + name + ".so")).is_file():
                errors.append("Missing NWNX plugin: " + name)
        if not (native / "runtime").is_dir():
            errors.append("Missing native/runtime directory")
    return errors


def install(args):
    world = identifier(args.world_id)
    root = args.target.expanduser().absolute()
    if any(c in str(root) for c in ("\n", "\r", '"', "%", "\\")):
        raise ValueError("Unsupported character in installation path")
    root = root.resolve()
    unit_name = "roleweaver-" + world + ".service"
    active = (
        subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", unit_name]
        ).returncode
        == 0
    )
    if active:
        raise ValueError("Stop " + unit_name + " before installing or upgrading")
    if (root / "config.json").exists():
        config = json.loads((root / "config.json").read_text())
        if config.get("world_id") != world:
            raise ValueError("Target belongs to a different world")
    else:
        config = json.loads((SOURCE / "config.example.json").read_text())
        config.update(
            world_id=world,
            world_name=world,
            redis_prefix=args.redis_prefix or "roleweaver:" + world,
            redis_port=args.redis_port,
            web_port=args.port,
            placement_owner="world",
        )
    if not re.fullmatch(r"[a-zA-Z0-9_:-]{1,80}", config["redis_prefix"]):
        raise ValueError("Invalid Redis prefix")
    if not 1024 <= int(config["web_port"]) <= 65535:
        raise ValueError("Dashboard port must be 1024-65535")
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", int(config["web_port"])))
        except OSError:
            raise ValueError(
                "Dashboard port is already in use; choose a different --port for a fresh install"
            )
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    if (root / "data/roleweaver.sqlite3").exists():
        snapshots = root / "upgrade-backups"
        snapshots.mkdir(exist_ok=True)
        name = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        with (
            sqlite3.connect(root / "data/roleweaver.sqlite3") as db,
            sqlite3.connect(snapshots / (name + ".sqlite3")) as dest,
        ):
            db.backup(dest)
        if (root / "data/identity_salt").exists():
            shutil.copy2(
                root / "data/identity_salt", snapshots / (name + ".identity_salt")
            )
    release = root / "releases" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    release.mkdir(parents=True)
    shutil.copytree(
        SOURCE / "roleweaver",
        release / "roleweaver",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for document in ("INSTALL_COMPANION.md", "INTEGRATION.md", "BACKUP_RESTORE.md"):
        if (SOURCE / "docs" / document).exists():
            shutil.copy2(SOURCE / "docs" / document, release / document)
    if not (root / "config.json").exists():
        (root / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    env = root / "provider.env"
    if not env.exists():
        env.write_text(
            "# Optional provider credential; never put this file in a source package.\n# ROLEWEAVER_API_KEY=your-key-here\n"
        )
    os.chmod(env, 0o600)
    os.chmod(root / "config.json", 0o600)
    current = root / "current"
    if current.exists() and not current.is_symlink():
        raise ValueError("current must be a managed symlink")
    if current.is_symlink():
        previous = root / "previous"
        if previous.is_symlink():
            previous.unlink()
        previous.symlink_to(current.resolve(), target_is_directory=True)
    temp = root / "current.new"
    if temp.is_symlink():
        temp.unlink()
    temp.symlink_to(release, target_is_directory=True)
    os.replace(temp, current)
    unit = root / unit_name
    unit.write_text(
        "[Unit]\nDescription=Role Weaver companion ("
        + world
        + ")\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory="
        + str(current)
        + "\nEnvironmentFile="
        + str(env)
        + '\nExecStart="'
        + sys.executable
        + '" -m roleweaver.web --config "'
        + str(root / "config.json")
        + '"\nRestart=on-failure\nRestartSec=3\nUMask=0077\nNoNewPrivileges=true\n\n[Install]\nWantedBy=default.target\n'
    )
    print("Installed companion at", root)
    print(
        "Config and existing data preserved. Provider remains as configured (offline on a new install)."
    )
    print("Register/start with:")
    print('systemctl --user link "' + str(unit) + '"')
    print("systemctl --user daemon-reload")
    print("systemctl --user enable --now " + unit_name)
    print("Dashboard: http://127.0.0.1:" + str(config["web_port"]))
    print(
        "Bridge must use world ID "
        + world
        + " and Redis prefix "
        + config["redis_prefix"]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"))
    parser.add_argument("--world-id", required=True)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-prefix")
    parser.add_argument(
        "--native",
        type=Path,
        help="Optional native installation containing runtime/ and plugins/",
    )
    args = parser.parse_args()
    try:
        identifier(args.world_id)
        if args.target is None:
            args.target = Path.home() / ".local/share/roleweaver" / args.world_id
        errors = check(args)
        if errors:
            raise ValueError("Preflight failed:\n- " + "\n- ".join(errors))
        if args.action == "check":
            print(
                "Companion prerequisites passed. Plugin presence does not prove they are loaded; check the NWNX startup log."
            )
        else:
            os.umask(0o077)
            install(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
