"""Transactional service updates. Never stop NWN or overwrite modules/plugins.

Each update has a private journal and a verified data recovery point. Rollback
selects previous application code and its Python environment, retaining current
configuration and player data. Database restoration remains an explicit recovery
operation. A failed/interrupted update returns to its recorded service version.
"""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

import install_profile as profiles
from roleweaver.db_recovery import DatabaseRecovery, atomic_json
from roleweaver.recovery_runtime import InstanceLock
from roleweaver.dashboard_auth import probe_headers


def run(args, **kwargs):
    return subprocess.run([str(v) for v in args], check=True, **kwargs)


def unit_name(p):
    return "roleweaver-" + p["world_id"] + ".service"


def active(p):
    return (
        subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", unit_name(p)],
            capture_output=True,
        ).returncode
        == 0
    )


def stop(p):
    """Also accept a removed/rejected unit only when no service process exists."""
    try:
        run(["systemctl", "--user", "stop", unit_name(p)])
    except subprocess.CalledProcessError:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit_name(p),
                "--property=MainPID",
                "--value",
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() != "0":
            raise


def own_service(p):
    root = profiles.installation(p["world_id"])
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit_name(p),
            "--property=FragmentPath",
            "--value",
        ],
        capture_output=True,
        text=True,
    )
    fragment = result.stdout.strip()
    if fragment and Path(fragment).resolve() != (root / unit_name(p)).resolve():
        raise ValueError(
            "A service with this world ID belongs to another installation; select a different world ID"
        )
    if (root / unit_name(p)).is_symlink():
        raise ValueError(
            "The managed service file must not redirect outside this installation"
        )


def release_path(root, value):
    path = Path(value).resolve()
    if (
        not path.is_relative_to((root / "releases").resolve())
        or path == (root / "releases").resolve()
        or not (path / "roleweaver").is_dir()
    ):
        raise ValueError("Recorded release is not a valid managed application folder")
    return path


def set_current(root, target):
    target = release_path(root, target)
    link = root / (".current-" + secrets.token_hex(8))
    link.symlink_to(target, target_is_directory=True)
    os.replace(link, root / "current")


def health(port, timeout=20, config_path=None):
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/health",
                    headers=probe_headers(config_path) if config_path else {},
                ),
                timeout=2,
            ) as response:
                value = json.load(response)
            if (
                value.get("components", {}).get("companion", {}).get("state")
                == "healthy"
            ):
                return value
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise ValueError(
                "Role Weaver did not pass its startup health check; review the service journal and Database & Recovery"
            )
        time.sleep(0.5)


def snapshot(p):
    root = profiles.installation(p["world_id"])
    with InstanceLock(root / "data"):
        recovery = DatabaseRecovery(root / "data", p["world_id"])
        recovery.rollback_interrupted()
        if (root / "data/roleweaver.sqlite3").exists():
            point = recovery.create(reason="before-software-change")
            return point["name"]
    return ""


def record(p):
    root = profiles.installation(p["world_id"])
    current = root / "current"
    if current.exists() and not current.is_symlink():
        raise ValueError("current must be a managed symlink")
    previous = (
        str(release_path(root, current.resolve())) if current.is_symlink() else ""
    )
    unit = root / unit_name(p)
    return dict(
        version=1,
        world=p["world_id"],
        before_release=previous,
        before_unit=unit.read_text() if unit.exists() else "",
        was_active=active(p),
        was_enabled=subprocess.run(
            ["systemctl", "--user", "is-enabled", "--quiet", unit_name(p)],
            capture_output=True,
        ).returncode
        == 0,
        state="prepared",
        recovery_point="",
    )


def restore_service(p, data):
    """Restore software only. Keep config, credentials and all database changes."""
    root = profiles.installation(p["world_id"])
    if data.get("version") != 1 or data.get("world") != p["world_id"]:
        raise ValueError("Software recovery journal does not match this world")
    old = release_path(root, data["before_release"]) if data["before_release"] else None
    own_service(p)
    if old or (root / unit_name(p)).exists():
        stop(p)
    if old:
        set_current(root, old)
        (root / unit_name(p)).write_text(data["before_unit"])
        run(["systemctl", "--user", "daemon-reload"])
        if data.get("was_enabled", False):
            run(["systemctl", "--user", "link", root / unit_name(p)])
            run(["systemctl", "--user", "enable", unit_name(p)])
        else:
            subprocess.run(
                ["systemctl", "--user", "disable", unit_name(p)], capture_output=True
            )
            run(["systemctl", "--user", "link", root / unit_name(p)])
        if data["was_active"]:
            run(["systemctl", "--user", "start", unit_name(p)])
            health(p["dashboard_port"], config_path=root / "config.json")
    else:
        # Failed fresh installation: retain files/data for diagnosis, but do not
        # leave a restart-on-failure service running against a partial install.
        subprocess.run(
            ["systemctl", "--user", "disable", unit_name(p)], capture_output=True
        )


def recover_pending(p):
    root = profiles.installation(p["world_id"])
    journal = root / "setup-pending.json"
    if journal.exists():
        data = json.loads(journal.read_text())
        print("Recovering an interrupted software operation for", p["world_id"])
        restore_service(p, data)
        journal.unlink()
        print("Previous software service state restored. Player data was retained.")


def environment(root, guardrails):
    """Versioned venvs outlive downloaded packages and remain available to rollback."""
    dest = root / "environments" / (str(time.time_ns()) + "-" + secrets.token_hex(4))
    try:
        run([sys.executable, "-m", "venv", dest])
    except subprocess.CalledProcessError:
        raise ValueError(
            "Python environment creation failed. On Ubuntu install python3-venv, then run setup again."
        ) from None
    python = dest / "bin/python"
    if guardrails:
        run(
            [
                python,
                "-m",
                "pip",
                "install",
                "-r",
                profiles.ROOT / "requirements-guardrails.txt",
            ]
        )
    return python


def apply(p, update=False):
    profiles.validate(p)
    installed = profiles.installed_settings(p)
    if update != bool(installed):
        raise ValueError(
            "Use update for an installed world, or install for a new world"
        )
    root = profiles.installation(p["world_id"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with InstanceLock(root / "setup-lock"):
        own_service(p)
        recover_pending(p)
        # Prepare dependencies before stopping an existing working service.
        guardrails = (
            bool(installed.get("guardrails_ai", False))
            if installed
            else p["features"]["guardrails"]
        )
        python = environment(root, guardrails)
        data = record(p)
        archive = root / "update-backups" / (str(time.time_ns()) + ".json")
        archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        journal = root / "setup-pending.json"
        atomic_json(journal, data)
        try:
            if installed:
                stop(p)
            data["recovery_point"] = snapshot(p)
            atomic_json(journal, data)
            args = [
                python,
                profiles.ROOT / "tools/install_companion.py",
                "install",
                "--world-id",
                p["world_id"],
                "--port",
                p["dashboard_port"],
                "--redis-port",
                p["redis_port"],
                "--redis-prefix",
                p["redis_prefix"],
            ]
            for key, flag in (
                ("companions", "--enable-companions"),
                ("dm_spawn", "--enable-dm-spawn"),
                ("persistent_spawn", "--enable-persistent-spawn"),
                ("guardrails", "--guardrails"),
            ):
                if p["features"][key]:
                    args.append(flag)
            run(args)
            run(["systemctl", "--user", "link", root / unit_name(p)])
            run(["systemctl", "--user", "daemon-reload"])
            run(["systemctl", "--user", "enable", unit_name(p)])
            run(["systemctl", "--user", "start", unit_name(p)])
            health(p["dashboard_port"], config_path=root / "config.json")
            data.update(
                state="complete", after_release=str((root / "current").resolve())
            )
            atomic_json(archive, data)
            journal.unlink()
        except Exception:
            restore_service(p, data)
            journal.unlink(missing_ok=True)
            raise
    p["progress"]["installed"] = data["after_release"]
    profiles.save(p)
    print(
        "Role Weaver service is healthy. NWN was not restarted. Software record:",
        archive,
    )
    print(
        "Current config, provider keys and player data were preserved."
        if update
        else "Configure your provider in LLM Settings after the offline connection test."
    )


def rollback_candidate(p):
    root = profiles.installation(p["world_id"])
    current = str((root / "current").resolve())
    for path in sorted((root / "update-backups").glob("*.json"), reverse=True):
        data = json.loads(path.read_text())
        if (
            data.get("state") == "complete"
            and data.get("after_release") == current
            and data.get("before_release")
        ):
            release_path(root, data["before_release"])
            return path, data
    raise ValueError(
        "No earlier managed software update is available to roll back. Legacy/manual installs need their original rollback procedure."
    )


def rollback(p):
    profiles.installed_settings(p)
    root = profiles.installation(p["world_id"])
    with InstanceLock(root / "setup-lock"):
        own_service(p)
        recover_pending(p)
        archive, previous = rollback_candidate(p)
        before = record(p)
        journal = root / "setup-pending.json"
        atomic_json(journal, before)
        try:
            stop(p)
            before["recovery_point"] = snapshot(p)
            atomic_json(journal, before)
            restore_service(p, dict(previous, was_active=before["was_active"]))
            previous["state"] = "rolled_back"
            atomic_json(archive, previous)
            journal.unlink()
        except Exception:
            restore_service(p, before)
            journal.unlink(missing_ok=True)
            raise
    p["progress"]["installed"] = str((root / "current").resolve())
    profiles.save(p)
    print(
        "Previous Role Weaver software restored. Current configuration, memories and translations were retained."
    )
    print(
        "Game scripts/plugins were not changed. Check their compatibility with the restored software before resuming gameplay."
    )
