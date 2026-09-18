"""Rotating, atomic recovery files in the dashboard's portable backup format."""

import datetime
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from . import backup

NAME = re.compile(r"(?:recent-\d{8}T\d{12}Z-[0-9a-f]{8}|daily-\d{8})\.json")


class RecoveryBackups:
    def __init__(self, directory, snapshot, config):
        self.directory = Path(directory)
        self.snapshot = snapshot
        self.enabled = config.get("recovery_backups", True) is not False
        self.interval = max(60, int(config.get("recovery_interval_seconds", 300)))
        self.keep_recent = max(1, int(config.get("recovery_keep_recent", 12)))
        self.keep_daily = max(1, int(config.get("recovery_keep_daily", 7)))
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.last_success = None
        self.error = ""
        self.next_attempt = 0

    def start(self):
        if self.enabled:
            self.thread = threading.Thread(
                target=self.run, daemon=True, name="recovery-backups"
            )
            self.thread.start()

    def run(self):
        while not self.stop.is_set():
            self.tick()
            self.stop.wait(1)

    def atomic_write(self, path, raw):
        temporary = self.directory / (".writing-" + secrets.token_hex(12))
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            if os.name == "posix":
                fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            if temporary.exists():
                temporary.unlink()

    def tick(self, now=None, clock=None):
        clock = time.monotonic() if clock is None else clock
        if not self.enabled or clock < self.next_attempt:
            return False
        now = time.time() if now is None else now
        try:
            # Snapshot first: never hold the filesystem lock while asking the service for its data.
            data = self.snapshot()
            backup.validate(data)
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(raw) > backup.LIMIT:
                raise ValueError("Backup exceeds the dashboard's 32 MB restore limit")
            date = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
            with self.lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                os.chmod(self.directory, 0o700)
                self.atomic_write(
                    self.directory
                    / (
                        date.strftime("recent-%Y%m%dT%H%M%S%fZ-")
                        + secrets.token_hex(4)
                        + ".json"
                    ),
                    raw,
                )
                daily = self.directory / date.strftime("daily-%Y%m%d.json")
                if not daily.exists():
                    self.atomic_write(daily, raw)
                # Never delete older snapshots until a new snapshot has been safely written.
                for prefix, count in (
                    ("recent-", self.keep_recent),
                    ("daily-", self.keep_daily),
                ):
                    paths = sorted(
                        (
                            p
                            for p in self.directory.iterdir()
                            if NAME.fullmatch(p.name)
                            and p.name.startswith(prefix)
                            and p.is_file()
                            and not p.is_symlink()
                        ),
                        reverse=True,
                    )
                    for old in paths[count:]:
                        old.unlink()
                self.last_success = now
                self.error = ""
            self.next_attempt = clock + self.interval
            return True
        except Exception as exc:
            with self.lock:
                self.error = "Recovery backup failed: " + str(exc)
            self.next_attempt = clock + 60
            return False

    def status(self):
        with self.lock:
            files = []
            if self.directory.exists():
                for p in self.directory.iterdir():
                    if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink():
                        stat = p.stat()
                        files.append(
                            dict(name=p.name, size=stat.st_size, created=stat.st_mtime)
                        )
            files.sort(key=lambda p: p["created"], reverse=True)
            last = self.last_success or (files[0]["created"] if files else None)
            return dict(
                enabled=self.enabled,
                interval_seconds=self.interval,
                keep_recent=self.keep_recent,
                keep_daily=self.keep_daily,
                last_success=last,
                error=self.error,
                files=files,
            )

    def read(self, name):
        with self.lock:
            if not isinstance(name, str) or not NAME.fullmatch(name):
                raise ValueError("Invalid recovery file name")
            p = self.directory / name
            if p.is_symlink() or not p.is_file():
                raise ValueError("Recovery file is no longer available")
            return p.read_bytes()
