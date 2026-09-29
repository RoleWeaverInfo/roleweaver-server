"""Recovery lifecycle, deliberately usable without opening application databases.

All database replacement passes through one maintenance gate: reject new HTTP
work, drain current requests and background writers, preserve original files,
close SQLite, then swap validated files. A journal rolls back interrupted swaps.
"""

from contextlib import contextmanager
import copy
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import threading
import time

from .db_recovery import DatabaseRecovery, DATABASES, digest
from .service import Service
from .redis_wire import Redis


class InstanceLock:
    """An OS lock is released on a crash; a leftover lock file is harmless."""

    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.file = open(directory / ".roleweaver.lock", "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if self.file.seek(0, 2) == 0:
                    self.file.write(b"0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise ValueError(
                "Another Role Weaver process is using this data folder. Stop it before continuing."
            ) from None

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class RecoveryRuntime:
    def __init__(self, directory, config, start_workers=True):
        self.directory = Path(directory)
        self.config = copy.deepcopy(config)
        self.instance = InstanceLock(directory)
        self.manager = DatabaseRecovery(directory, config.get("world_id", "default"))
        self.condition = threading.Condition(threading.RLock())
        self.active = 0
        self.maintenance = False
        self.app = None
        self.error = ""
        self.job = dict(running=False, label="", error="", result=None)
        self.job_thread = None
        self.stop = threading.Event()
        self.scheduler = None
        self.workers = start_workers
        self.previews = {}
        self.files = []
        self.health = {}
        self.next_backup = time.monotonic() + 10
        try:
            self.manager.rollback_interrupted()
            self._open()
        except Exception as exc:
            self.error = self.failure(exc)
        self.refresh()

    @staticmethod
    def failure(exc):
        # No provider replies, config files or credentials in recovery diagnostics.
        if isinstance(exc, (ValueError, OSError)):
            return str(exc)[:500]
        return (
            type(exc).__name__
            + ": database operation failed; check database health and the recovery guide."
        )

    def refresh(self):
        self.health = self.manager.health()
        self.files = self.manager.files()

    def _open(self):
        self.health = self.manager.health()
        if any(not v["ok"] for v in self.health.values()):
            raise ValueError(
                "A database failed its startup check. Restore a verified recovery point below."
            )
        # Missing world/identity files in an established installation are data
        # loss, not permission to create an empty world and a new player salt.
        established = (self.directory / "identity_salt").exists() or bool(
            self.manager.files()
        )
        if established and self.health["world"].get("missing"):
            raise ValueError(
                "The world database is missing. Restore it instead of creating an empty world."
            )
        if (
            not self.health["world"].get("missing")
            and not (self.directory / "identity_salt").is_file()
        ):
            raise ValueError(
                "Player identity file is missing. Restore all databases together."
            )
        known = {
            kind
            for point in self.manager.files()
            for kind in point.get("databases", {})
        }
        if any(self.health[k].get("missing") for k in known):
            raise ValueError(
                "A previously backed-up database is missing. Restore a recovery point before continuing."
            )
        app = Service.__new__(Service)
        try:
            Service.__init__(app, self.directory, copy.deepcopy(self.config))
            app.database_recovery = self.manager
            app.translations  # Check the cache before allowing requests/starting workers.
            # SQLite integrity alone cannot detect malformed JSON in saved
            # profiles/settings. Exercise the persisted data needed by the UI
            # before committing a restore or reporting the companion available.
            app.snapshot()
            app.store.world_documents()
            app.store.access_lore()
            app.translations.config()
            app.usage.settings()
            if not re.fullmatch(r"[0-9a-f]{64}", app.salt):
                raise ValueError(
                    "Player identity salt is invalid; restore all databases together"
                )
            if self.workers:
                app.start()
        except BaseException:
            app.close()
            raise
        self.app = app
        self.error = ""

    @contextmanager
    def lease(self):
        with self.condition:
            if self.maintenance or self.app is None:
                raise ValueError(
                    "Database recovery is active. Open /recovery to inspect or restore the data."
                )
            self.active += 1
            app = self.app
        try:
            yield app
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()

    def status(self):
        with self.condition:
            return dict(
                available=self.app is not None,
                maintenance=self.maintenance,
                error=self.error,
                warning=self.manager.last_error,
                health=copy.deepcopy(self.health),
                files=copy.deepcopy(self.files),
                settings=dict(self.manager.config),
                job=copy.deepcopy(self.job),
                backup_bytes=sum(f["bytes"] for f in self.files),
                free_bytes=shutil.disk_usage(self.directory).free,
                next_backup_seconds=max(0, int(self.next_backup - time.monotonic())),
            )

    def submit(self, label, callback):
        with self.condition:
            if self.job["running"] or self.stop.is_set():
                raise ValueError(
                    "Another recovery operation is running; wait for it to finish"
                )
            self.job = dict(running=True, label=label, error="", result=None)

            def run():
                result, error = None, ""
                try:
                    result = callback()
                except Exception as exc:
                    error = self.failure(exc)
                finally:
                    try:
                        self.refresh()
                    except Exception as exc:
                        error = error or self.failure(exc)
                    with self.condition:
                        self.job = dict(
                            running=False, label=label, error=error, result=result
                        )
                        self.condition.notify_all()

            self.job_thread = threading.Thread(
                target=run, daemon=True, name="database-recovery"
            )
            self.job_thread.start()
        return dict(accepted=True)

    def start(self):
        def schedule():
            while not self.stop.wait(2):
                if self.app is None or self.maintenance or self.job["running"]:
                    continue
                if time.monotonic() >= self.next_backup:
                    self.next_backup = (
                        time.monotonic() + self.manager.config["interval_minutes"] * 60
                    )
                    try:
                        if self.manager.config["enabled"]:

                            def snapshot_checked():
                                result = self.check()
                                if self.app is None:
                                    raise ValueError(
                                        "Database check failed; automatic backup skipped. Existing recovery points are preserved."
                                    )
                                return self.capture("scheduled")

                            self.submit("Automatic snapshot", snapshot_checked)
                        else:
                            self.submit("Scheduled health check", self.check)
                    except ValueError:
                        pass

        self.scheduler = threading.Thread(
            target=schedule, daemon=True, name="database-scheduler"
        )
        self.scheduler.start()

    def capture(self, reason="manual"):
        with self.lease() as app:
            return self.manager.create(app, reason)

    def check(self):
        health = self.manager.health(full=True)
        if any(not v["ok"] for v in health.values()):
            self._enter_maintenance()
            if self.app:
                self.app.close()
                self.app = None
            self.error = "Database check failed. The companion is paused; originals are preserved. Restore a verified recovery point."
            self.maintenance = False
        return dict(health=health)

    def _enter_maintenance(self):
        with self.condition:
            self.maintenance = True
            while self.active:
                self.condition.wait(1)

    def preview(self, name, scope):
        salt = (
            self.app.salt
            if self.app
            else (
                (self.directory / "identity_salt").read_text().strip()
                if (self.directory / "identity_salt").exists()
                else ""
            )
        )
        stage, kinds = self.manager.begin_restore(name, scope, salt)
        try:
            summary = json.loads((stage / "manifest.json").read_text())
            token = secrets.token_urlsafe(24)
            self.previews = {
                token: (time.monotonic(), name, scope, digest(self.manager.path(name)))
            }
            return dict(
                token=token,
                name=name,
                scope=scope,
                databases={k: summary["databases"][k] for k in kinds},
                created=summary["created"],
                warning="Stop the NWN server first. Restore replaces saved data and loses changes after this snapshot. NWN characters, inventories and campaign databases are not restored.",
            )
        finally:
            shutil.rmtree(stage)

    def restore(self, token, game_stopped):
        if game_stopped is not True:
            raise ValueError("Stop NWN and confirm it is stopped before restoring")
        entry = self.previews.pop(token, None)
        if not entry or time.monotonic() - entry[0] > 600:
            raise ValueError(
                "Restore preview expired; preview the recovery point again"
            )
        _, name, scope, checksum = entry
        if digest(self.manager.path(name)) != checksum:
            raise ValueError("Recovery point changed since preview; preview it again")
        app = self.app
        if app and time.monotonic() - app.conversation_hello.get("seen", -1e9) < 30:
            raise ValueError(
                "The game bridge is still active. Stop NWN, wait 30 seconds and preview again."
            )
        salt = (
            app.salt
            if app
            else (
                (self.directory / "identity_salt").read_text().strip()
                if (self.directory / "identity_salt").exists()
                else ""
            )
        )
        stage, kinds = self.manager.begin_restore(name, scope, salt)
        quarantine = None
        try:
            self._enter_maintenance()
            if app:
                app.quiesce()
            if self.workers:
                # NWN is stopped. Buffered events/commands from the old game
                # must not replay into the restored database when workers resume.
                try:
                    redis = Redis(port=self.config.get("redis_port", 6379))
                    prefix = self.config.get("redis_prefix", "roleweaver:v1")
                    redis.call("DEL", prefix + ":events", prefix + ":commands")
                except (OSError, ConnectionError, ValueError):
                    raise ValueError(
                        "Redis must be reachable to clear old game commands before restore. Start Redis, keep NWN stopped, then preview again."
                    ) from None
            # A usable current database gets its own protected undo snapshot.
            # Corrupt data is still preserved byte-for-byte in quarantine.
            if all(v["ok"] for v in self.manager.health().values()):
                self.manager.create(app, "before-restore")
            quarantine = self.manager.quarantine(kinds)
            if app:
                app.close()
            self.app = None
            self.manager.install_restore(stage, kinds, quarantine, scope)
            # Open before committing the journal. A valid SQLite file can still
            # contain application data that this version cannot load.
            original_workers = self.workers
            self.workers = False
            try:
                self._open()
            finally:
                self.workers = original_workers
            self.manager.finish_restore()
            if self.workers:
                self.app.start()
            return dict(
                restored=True,
                quarantine=quarantine.name,
                message="Restored. Start NWN when ready; reopen the dashboard and language menu.",
            )
        except BaseException:
            if self.app:
                self.app.close()
                self.app = None
            try:
                self.manager.rollback_interrupted()
                self._open()
            except Exception as exc:
                self.error = self.failure(exc)
            raise
        finally:
            self.maintenance = False
            shutil.rmtree(stage)

    def retry(self):
        if self.app:
            return dict(message="Companion is already running")
        self.manager.rollback_interrupted()
        self._open()
        return dict(message="Companion started")

    def close(self):
        self.stop.set()
        if self.scheduler:
            self.scheduler.join()
        if self.job_thread:
            self.job_thread.join()
        self._enter_maintenance()
        if self.app:
            self.app.close()
            self.app = None
        self.instance.close()
