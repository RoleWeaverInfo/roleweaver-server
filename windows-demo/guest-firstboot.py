#!/usr/bin/env python3
"""Initialize one portable demo installation, never an existing PW server.

The read-only FAT drive contains an instance ID and public SSH key only. Each
Windows folder gets its own writable disk, player identity, SSH host keys and
dashboard credentials. Existing saves are never seeded again on normal boots.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

HOME = Path("/home/roleweaver")
DEMO = HOME / "demo"
WORLD = DEMO / ".demo/qemu_demo"
STATE = Path("/var/lib/roleweaver/portable-instance.json")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(value) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def seed():
    """Runs as the unprivileged game user, in the bundled virtual environment."""
    sys.path.insert(0, str(DEMO))
    from demo.demo import seed_database
    from roleweaver.translation import TranslationCache

    data = WORLD / "data"
    if data.exists():
        # A completed atomic rename can precede an interrupted first-boot marker.
        if not (data / "identity_salt").is_file():
            raise RuntimeError("Existing demo data has no identity; restore its backup")
        return
    pending = WORLD / "firstboot-data"
    seed_database(
        pending / "roleweaver.sqlite3",
        json.loads((DEMO / "demo/content.json").read_text()),
        "qemu_demo",
    )
    cache = TranslationCache(pending / "translations.sqlite3")
    try:
        cache.configure(dict(cache.config(), enabled=True))
    finally:
        cache.db.close()
    pending.rename(data)


def initialize():
    if os.geteuid() != 0 or not (WORLD / "settings.json").is_file():
        raise RuntimeError("Portable demo image is not prepared")
    mount = Path("/run/roleweaver-bootstrap")
    mount.mkdir(exist_ok=True)
    device = "/dev/vdb1" if Path("/dev/vdb1").exists() else "/dev/vdb"
    subprocess.run(
        ["mount", "-t", "vfat", "-o", "ro,nosuid,nodev,noexec", device, str(mount)],
        check=True,
    )
    try:
        raw = (mount / "instance.json").read_bytes()
        if len(raw) > 8192:
            raise ValueError("Bootstrap file is too large")
        request = json.loads(raw)
    finally:
        subprocess.run(["umount", str(mount)], check=True)
    instance = request.get("instance", "")
    key = request.get("ssh_public_key", "")
    port = request.get("dashboard_port", 8747)
    if (
        request.get("version") != 1
        or type(port) is not int
        or not 1024 <= port <= 65535
        or port in (5127, 6379, 8748)
        or not re.fullmatch(r"[0-9a-f]{32}", instance)
        or not re.fullmatch(
            r"ssh-rsa [A-Za-z0-9+/=]{200,2000} roleweaver-local-demo", key
        )
    ):
        raise ValueError("Invalid portable installation identity")
    ready = False
    if STATE.exists():
        saved = json.loads(STATE.read_text())
        if saved.get("instance") != instance or saved.get("ssh_public_key") != key:
            raise RuntimeError(
                "The disk belongs to another installation; restore its matching userdata folder"
            )
        ready = saved.get("ready", False)
    elif (WORLD / "data").exists():
        raise RuntimeError(
            "Refusing to initialize an image containing existing user data"
        )
    # Host/Origin checks use the dashboard's real listening port. Keep that
    # port consistent with the user's Windows forward, including on later boots.
    for path in (WORLD / "config.json", WORLD / "settings.json"):
        owner = path.stat()
        value = json.loads(path.read_text())
        value["web_port"] = port
        write_json(path, value)
        os.chown(path, owner.st_uid, owner.st_gid)
    environment = Path("/run/roleweaver/dashboard.env")
    environment.parent.mkdir(exist_ok=True)
    environment.write_text(f"ROLEWEAVER_DASHBOARD_PORT={port}\n")
    if ready:
        return
    write_json(STATE, dict(instance=instance, ssh_public_key=key, ready=False))
    subprocess.run(
        [
            "runuser",
            "-u",
            "roleweaver",
            "--",
            str(DEMO / ".venv/bin/python"),
            __file__,
            "--seed",
        ],
        cwd=DEMO,
        check=True,
    )
    ssh = HOME / ".ssh"
    ssh.mkdir(mode=0o700, exist_ok=True)
    authorized = ssh / "authorized_keys"
    authorized.write_text(key + "\n")
    authorized.chmod(0o600)
    subprocess.run(["chown", "-R", "roleweaver:roleweaver", str(ssh)], check=True)
    subprocess.run(["ssh-keygen", "-A"], check=True)
    write_json(STATE, dict(instance=instance, ssh_public_key=key, ready=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--seed"]:
        seed()
    else:
        initialize()
