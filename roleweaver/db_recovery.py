"""Validated SQLite recovery points, independent of the application databases.

The runtime owns quiescing writers. This module owns bounded archives, checksums,
retention and a durable restore journal. Nothing here runs SQL from an upload.
"""

from contextlib import closing, ExitStack
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile

from . import __version__

DATABASES = {
    "world": "roleweaver.sqlite3",
    "translations": "translations.sqlite3",
    "usage": "usage.sqlite3",
}
REQUIRED = {
    "world": {
        "npcs": {"id", "profile"},
        "memories": {"npc", "player", "text", "created"},
        "messages": {"npc", "player", "text", "created", "speaker"},
        "placements": {"npc", "world", "placement"},
        "backup_settings": {"key", "value"},
    },
    "translations": {
        "entries": {
            "key",
            "source",
            "target",
            "kind",
            "original",
            "translated",
            "status",
            "revision",
        },
        "preferences": {"player", "enabled", "language"},
        "settings": {"key", "value"},
        "current_sources": {"source_id", "target", "key"},
    },
    "usage": {
        "requests": {"id", "created", "provider", "model", "phase", "status"},
        "prices": {"provider", "model", "rates"},
    },
}
DEFAULT = dict(
    enabled=True,
    interval_minutes=15,
    keep_recent=24,
    keep_daily=14,
    keep_weekly=8,
    max_storage_mb=2048,
    min_free_mb=256,
)
NAME = re.compile(r"db-\d{8}T\d{12}Z-[0-9a-f]{8}\.zip")
MAX_UPLOAD = 512 * 1024 * 1024
MAX_EXPANDED = 2 * 1024 * 1024 * 1024
MEMBERS = {*DATABASES.values(), "identity_salt", "manifest.json"}


def sync_directory(path):
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def durable_copy(source, target):
    """Publish one complete file on the target filesystem, preserving its predecessor."""
    target = Path(target)
    temporary = target.with_name(".writing-" + secrets.token_hex(12))
    try:
        with open(source, "rb") as src, open(temporary, "xb") as dst:
            os.chmod(temporary, 0o600)
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temporary, target)
        sync_directory(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(".writing-" + secrets.token_hex(12))
    try:
        with open(temporary, "x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def readonly(path):
    db = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5
    )
    db.execute("PRAGMA trusted_schema=OFF")
    db.execute("PRAGMA query_only=ON")
    return db


def check_database(path, kind, full=False):
    """Read the WAL too; immutable mode would silently miss committed live writes."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{DATABASES[kind]} is missing, empty or a symlink")
    deadline = time.monotonic() + 60
    with closing(readonly(path)) as db:
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        result = db.execute(
            "PRAGMA integrity_check" if full else "PRAGMA quick_check"
        ).fetchall()
        if result != [("ok",)]:
            raise ValueError(f"{DATABASES[kind]} failed its SQLite integrity check")
        objects = db.execute(
            "SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if any(type_ in ("trigger", "view") for _, type_ in objects):
            raise ValueError(
                "Unexpected database triggers or views; manual review required"
            )
        tables = {name for name, type_ in objects if type_ == "table"}
        for table, expected in REQUIRED[kind].items():
            if table not in tables:
                raise ValueError(f"{DATABASES[kind]} is missing table {table}")
            columns = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
            if not expected <= columns:
                raise ValueError(f"{DATABASES[kind]} has an unsupported {table} schema")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version != 0:
            raise ValueError(
                "Database schema is newer or unsupported by this application"
            )
        counts = {
            table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in REQUIRED[kind]
        }
        return dict(
            ok=True, bytes=path.stat().st_size, schema_version=version, records=counts
        )


def snapshot_connection(source, target):
    deadline = time.monotonic() + 60

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError(
                "Database snapshot timed out; existing recovery points are untouched"
            )

    with closing(sqlite3.connect(target)) as destination:
        source.backup(destination, pages=256, progress=progress, sleep=0.02)
        destination.execute("PRAGMA journal_mode=DELETE")
    os.chmod(target, 0o600)


class DatabaseRecovery:
    def __init__(self, directory, world):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.folder = self.directory / "database-backups"
        self.folder.mkdir(mode=0o700, exist_ok=True)
        self.world = world
        self.lock = threading.RLock()
        self.settings_path = self.directory / "database-recovery.json"
        self.journal = self.directory / "database-restore.json"
        self.last_error = ""
        self.config = dict(DEFAULT)
        if self.settings_path.exists():
            try:
                self.config = self.validate_settings(
                    json.loads(self.settings_path.read_text())
                )
            except (ValueError, OSError):
                self.last_error = "Backup settings could not be read; safe defaults are active. Save settings to repair this file."

    @staticmethod
    def validate_settings(value):
        if not isinstance(value, dict) or type(value.get("enabled")) is not bool:
            raise ValueError("Supply valid automatic backup settings")
        clean = dict(enabled=value["enabled"])
        for key, limits in {
            "interval_minutes": (5, 1440),
            "keep_recent": (2, 168),
            "keep_daily": (1, 90),
            "keep_weekly": (1, 52),
            "max_storage_mb": (32, 102400),
            "min_free_mb": (16, 102400),
        }.items():
            v = value.get(key, DEFAULT[key])
            if type(v) is not int or not limits[0] <= v <= limits[1]:
                raise ValueError(f"Invalid {key}: choose {limits[0]}–{limits[1]}")
            clean[key] = v
        return clean

    def configure(self, value):
        clean = self.validate_settings(value)
        with self.lock:
            atomic_json(self.settings_path, clean)
            self.config = clean
        return clean

    def path(self, name):
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError("Invalid recovery point")
        path = self.folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Recovery point is no longer available")
        return path

    def health(self, full=False):
        result = {}
        for kind, filename in DATABASES.items():
            path = self.directory / filename
            try:
                if not path.exists():
                    # Brand-new installs may not have created a cache/usage DB yet.
                    result[kind] = dict(ok=True, missing=True, bytes=0)
                else:
                    result[kind] = check_database(path, kind, full)
                    result[kind]["wal_bytes"] = (
                        Path(str(path) + "-wal").stat().st_size
                        if Path(str(path) + "-wal").exists()
                        else 0
                    )
            except (sqlite3.Error, OSError, ValueError) as exc:
                result[kind] = dict(ok=False, error=f"{type(exc).__name__}: {exc}")
        return result

    def space(self, needed=0):
        free = shutil.disk_usage(self.directory).free
        if free - needed < self.config["min_free_mb"] * 1024 * 1024:
            raise ValueError(
                "Not enough free disk space. Existing recovery points were kept; free space or adjust the reserve."
            )
        return free

    def create(self, app=None, reason="manual"):
        """Freeze app writers only while capturing SQLite snapshots, then compress."""
        with (
            self.lock,
            tempfile.TemporaryDirectory(prefix=".capture-", dir=self.folder) as temp,
        ):
            dest = Path(temp)
            estimated = sum(
                (self.directory / n).stat().st_size
                for n in DATABASES.values()
                if (self.directory / n).exists()
            )
            self.space(estimated * 2 + 1024 * 1024)
            with ExitStack() as locks:
                if app is not None:
                    locks.enter_context(app.lock)
                    cache = app.translations
                    for lock in (app.store.lock, cache.lock, app.usage.lock):
                        locks.enter_context(lock)
                    sources = {"world": app.store.db, "translations": cache.db}
                    salt = app.salt
                else:
                    sources = {}
                    salt = (self.directory / "identity_salt").read_text().strip()
                for kind, filename in DATABASES.items():
                    path = self.directory / filename
                    if not path.exists():
                        continue
                    if kind in sources:
                        snapshot_connection(sources[kind], dest / filename)
                    else:
                        with closing(readonly(path)) as source:
                            snapshot_connection(source, dest / filename)
                # The world DB may hold a newer salt from a legacy JSON restore.
                if (dest / DATABASES["world"]).exists():
                    with closing(readonly(dest / DATABASES["world"])) as db:
                        row = db.execute(
                            "SELECT value FROM backup_settings WHERE key='identity_salt'"
                        ).fetchone()
                        if row:
                            salt = row[0]
                if not re.fullmatch(r"[0-9a-f]{64}", salt):
                    raise ValueError("Player identity salt is missing or invalid")
                (dest / "identity_salt").write_text(salt, encoding="ascii")
            manifest = dict(
                format="roleweaver-database-recovery",
                version=1,
                application_version=__version__,
                world=self.world,
                created=time.time(),
                reason=reason,
                databases={},
                files={},
            )
            for kind, filename in DATABASES.items():
                if (dest / filename).exists():
                    manifest["databases"][kind] = check_database(
                        dest / filename, kind, True
                    )
            if "world" not in manifest["databases"]:
                raise ValueError("No world database to back up")
            for file in dest.iterdir():
                manifest["files"][file.name] = dict(
                    sha256=digest(file), bytes=file.stat().st_size
                )
            atomic_json(dest / "manifest.json", manifest)
            date = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            name = f"db-{date}-{secrets.token_hex(4)}.zip"
            archive = dest / "snapshot.zip"
            with zipfile.ZipFile(
                archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6
            ) as z:
                for filename in (*manifest["files"], "manifest.json"):
                    z.write(dest / filename, filename)
            if archive.stat().st_size > MAX_UPLOAD:
                raise ValueError(
                    "Snapshot exceeds the supported 512 MB archive size; archive history before retrying"
                )
            self._validate_archive(archive)
            # Reclaim only obsolete scheduled points, and only after a valid new
            # archive exists. Never remove manual/pre-upgrade/pre-restore points.
            self.prune(incoming=archive.stat().st_size)
            if (
                self.total_bytes() + archive.stat().st_size
                > self.config["max_storage_mb"] * 1024 * 1024
            ):
                raise ValueError(
                    "Backup storage limit reached. Download/delete older protected points or increase the limit."
                )
            durable_copy(archive, self.folder / name)
            self._record(name, protected=reason != "scheduled", verified=True)
            self.prune()
            self.last_error = ""
            return self.describe(name)

    def _metadata(self, name):
        try:
            value = json.loads((self.folder / (name + ".json")).read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _record(self, name, **changes):
        value = self._metadata(name)
        value.update(changes)
        if "verified" in changes:
            path = self.path(name)
            value.update(
                checked=time.time(),
                size=path.stat().st_size,
                mtime=path.stat().st_mtime_ns,
            )
        atomic_json(self.folder / (name + ".json"), value)

    def describe(self, name):
        path = self.path(name)
        meta = self._metadata(name)
        try:
            with zipfile.ZipFile(path) as z:
                info = z.getinfo("manifest.json")
                if info.file_size > 65536:
                    raise ValueError("Invalid manifest")
                m = json.loads(z.read(info))
                if (
                    not isinstance(m, dict)
                    or not isinstance(m.get("databases"), dict)
                    or not set(m["databases"]) <= set(DATABASES)
                    or not isinstance(m.get("created"), (int, float))
                    or not math.isfinite(m["created"])
                    or not 0 <= m["created"] <= 32503680000
                ):
                    raise ValueError("Invalid recovery manifest")
            return dict(
                name=name,
                created=m["created"],
                reason=m.get("reason", "import"),
                application_version=m.get("application_version", "unknown"),
                databases=m["databases"],
                bytes=path.stat().st_size,
                protected=meta.get("protected", True),
                checked=meta.get("checked"),
                verified=meta.get("verified", False)
                and meta.get("size") == path.stat().st_size
                and meta.get("mtime") == path.stat().st_mtime_ns,
                error=meta.get("error", ""),
            )
        except (ValueError, KeyError, TypeError, zipfile.BadZipFile, OSError):
            return dict(
                name=name,
                created=path.stat().st_mtime,
                bytes=path.stat().st_size,
                protected=True,
                verified=False,
                error="Unreadable recovery manifest",
                databases={},
            )

    def files(self):
        with self.lock:
            return sorted(
                (
                    self.describe(p.name)
                    for p in self.folder.iterdir()
                    if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()
                ),
                key=lambda row: row["created"],
                reverse=True,
            )

    def total_bytes(self):
        return sum(
            p.stat().st_size
            for p in self.folder.iterdir()
            if p.is_file() and not p.is_symlink()
        )

    def prune(self, incoming=0):
        rows = self.files()
        automatic = [r for r in rows if not r["protected"] and r["verified"]]
        keep = {r["name"] for r in automatic[: self.config["keep_recent"]]}
        for bucket, count in (
            ("%Y-%m-%d", self.config["keep_daily"]),
            ("%G-%V", self.config["keep_weekly"]),
        ):
            periods = set()
            for row in automatic:
                period = dt.datetime.fromtimestamp(
                    row["created"], dt.timezone.utc
                ).strftime(bucket)
                if period not in periods and len(periods) < count:
                    periods.add(period)
                    keep.add(row["name"])
        for row in reversed(automatic):
            if row["name"] not in keep:
                self._remove(row["name"])
        # The size budget never silently overrides selected retention/protection.

    def _remove(self, name):
        self.path(name).unlink()
        (self.folder / (name + ".json")).unlink(missing_ok=True)
        sync_directory(self.folder)

    def protect(self, name, enabled):
        if type(enabled) is not bool:
            raise ValueError("Invalid protection setting")
        with self.lock:
            self.path(name)
            self._record(name, protected=enabled)

    def delete(self, name):
        with self.lock:
            row = self.describe(name)
            if row["protected"]:
                raise ValueError("Unprotect this recovery point before deleting it")
            good = [r for r in self.files() if r["verified"]]
            if row["verified"] and len(good) <= 1:
                raise ValueError("Keep at least one verified recovery point")
            self._remove(name)

    def _validate_archive(self, path, output=None):
        with tempfile.TemporaryDirectory(prefix=".verify-", dir=self.folder) as temp:
            dest = Path(output or temp)
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                names = [i.filename for i in infos]
                if (
                    len(names) != len(set(names))
                    or not set(names) <= MEMBERS
                    or not {"manifest.json", "identity_salt", DATABASES["world"]}
                    <= set(names)
                ):
                    raise ValueError(
                        "Archive contains unexpected, duplicate or missing files"
                    )
                if (
                    sum(i.file_size for i in infos) > MAX_EXPANDED
                    or z.getinfo("manifest.json").file_size > 65536
                    or z.getinfo("identity_salt").file_size > 128
                ):
                    raise ValueError("Expanded recovery point is too large")
                self.space(sum(i.file_size for i in infos))
                m = json.loads(z.read("manifest.json"))
                if (
                    not isinstance(m, dict)
                    or not isinstance(m.get("files"), dict)
                    or not isinstance(m.get("databases"), dict)
                ):
                    raise ValueError("Invalid recovery manifest")
                if (
                    m.get("format") != "roleweaver-database-recovery"
                    or m.get("version") != 1
                    or m.get("world") != self.world
                ):
                    raise ValueError(
                        "Recovery point belongs to another world or uses an unsupported format"
                    )
                if set(m.get("files", {})) != set(names) - {"manifest.json"} or set(
                    m.get("databases", {})
                ) != {k for k, n in DATABASES.items() if n in names}:
                    raise ValueError("Manifest does not match archive contents")
                for info in infos:
                    if info.filename == "manifest.json":
                        continue
                    target = dest / info.filename
                    with z.open(info) as source, target.open("xb") as out:
                        shutil.copyfileobj(source, out)
                    declared = m["files"][info.filename]
                    if not isinstance(declared, dict):
                        raise ValueError("Invalid recovery checksum manifest")
                    if declared["bytes"] != target.stat().st_size or declared[
                        "sha256"
                    ] != digest(target):
                        raise ValueError("Recovery point checksum mismatch")
                salt = (dest / "identity_salt").read_text().strip()
                if not re.fullmatch(r"[0-9a-f]{64}", salt):
                    raise ValueError("Recovery point contains an invalid identity salt")
                for kind in m["databases"]:
                    check_database(dest / DATABASES[kind], kind, True)
                with closing(readonly(dest / DATABASES["world"])) as db:
                    row = db.execute(
                        "SELECT value FROM backup_settings WHERE key='identity_salt'"
                    ).fetchone()
                    if row and row[0] != salt:
                        raise ValueError(
                            "Recovery point has inconsistent player identity data"
                        )
                if output is not None:
                    atomic_json(dest / "manifest.json", m)
                return m

    def verify(self, name):
        with self.lock:
            try:
                self._validate_archive(self.path(name))
                self._record(name, verified=True, error="")
            except Exception as exc:
                self._record(name, verified=False, error=str(exc))
                raise
            return self.describe(name)

    def import_archive(self, source):
        with self.lock:
            if Path(source).stat().st_size > MAX_UPLOAD:
                raise ValueError("Recovery archive exceeds 512 MB")
            self._validate_archive(source)
            if (
                self.total_bytes() + Path(source).stat().st_size
                > self.config["max_storage_mb"] * 1024 * 1024
            ):
                raise ValueError("Backup storage limit reached")
            name = (
                "db-"
                + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-")
                + secrets.token_hex(4)
                + ".zip"
            )
            durable_copy(source, self.folder / name)
            self._record(name, protected=True, verified=True)
            return self.describe(name)

    def quarantine(self, kinds):
        root = self.directory / "database-quarantine"
        root.mkdir(mode=0o700, exist_ok=True)
        dest = root / (str(time.time_ns()) + "-" + secrets.token_hex(4))
        dest.mkdir(mode=0o700)
        entries = {}
        for filename in [
            DATABASES[k] + suffix for k in kinds for suffix in ("", "-wal", "-shm")
        ] + ["identity_salt"]:
            source = self.directory / filename
            if source.is_symlink():
                raise ValueError("Refusing a symlink in database storage")
            entries[filename] = source.exists()
            if source.exists():
                durable_copy(source, dest / filename)
        atomic_json(dest / "files.json", entries)
        return dest

    def begin_restore(self, name, scope, salt):
        """Validate to fresh files before any live database is moved. Caller stopped writers."""
        if scope not in ("all", "translations"):
            raise ValueError("Choose all databases or translations only")
        stage = Path(tempfile.mkdtemp(prefix=".restore-", dir=self.directory))
        try:
            m = self._validate_archive(self.path(name), stage)
            kinds = list(m["databases"]) if scope == "all" else ["translations"]
            if any(k not in m["databases"] for k in kinds):
                raise ValueError("Recovery point does not include that database")
            if (
                scope == "translations"
                and (stage / "identity_salt").read_text().strip() != salt
            ):
                raise ValueError(
                    "Translation preferences belong to a different identity salt; restore all databases together"
                )
            # Never synthesize missing world data. Cache/usage absent from an older
            # point remain current; every file to be replaced is listed explicitly.
            return stage, kinds
        except BaseException:
            shutil.rmtree(stage)
            raise

    def install_restore(self, stage, kinds, quarantine, scope):
        state = dict(
            version=1,
            quarantine=quarantine.name,
            kinds=kinds,
            scope=scope,
            phase="installing",
        )
        atomic_json(self.journal, state)
        for kind in kinds:
            path = self.directory / DATABASES[kind]
            for suffix in ("-wal", "-shm"):
                Path(str(path) + suffix).unlink(missing_ok=True)
            durable_copy(stage / DATABASES[kind], path)
        if scope == "all":
            durable_copy(stage / "identity_salt", self.directory / "identity_salt")
        state["phase"] = "installed"
        atomic_json(self.journal, state)

    def finish_restore(self):
        self.journal.unlink(missing_ok=True)
        sync_directory(self.directory)

    def rollback_interrupted(self):
        """If a crash split a multi-file swap, restore the preserved original set."""
        if not self.journal.exists():
            return False
        state = json.loads(self.journal.read_text())
        name = state.get("quarantine", "")
        if not re.fullmatch(r"\d+-[0-9a-f]{8}", name):
            raise ValueError("Invalid restore journal; manual recovery required")
        source = self.directory / "database-quarantine" / name
        if source.is_symlink() or source.parent.is_symlink():
            raise ValueError("Invalid quarantine location")
        files = json.loads((source / "files.json").read_text())
        allowed = {
            n + suffix for n in DATABASES.values() for suffix in ("", "-wal", "-shm")
        } | {"identity_salt"}
        if (
            not isinstance(files, dict)
            or not files
            or not set(files) <= allowed
            or any(type(v) is not bool for v in files.values())
        ):
            raise ValueError("Invalid quarantine manifest")
        for filename, existed in files.items():
            if existed and (
                not (source / filename).is_file() or (source / filename).is_symlink()
            ):
                raise ValueError(
                    "A preserved original is missing; manual recovery required"
                )
        for filename, existed in files.items():
            target = self.directory / filename
            if existed:
                durable_copy(source / filename, target)
            else:
                target.unlink(missing_ok=True)
        self.finish_restore()
        self.last_error = "An interrupted restore was rolled back. Original files remain in quarantine; choose a verified recovery point to retry."
        return True
