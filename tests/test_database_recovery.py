"""Recovery tests use disposable worlds; never restore a developer's game data."""

import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from roleweaver.db_recovery import (
    DatabaseRecovery,
    DATABASES,
    DEFAULT,
    check_database,
    digest,
)
from roleweaver.recovery_runtime import RecoveryRuntime, InstanceLock


class DatabaseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.config = dict(
            provider="offline", world_id="test_world", api_key="NEVER EXPORT THIS"
        )
        self.runtime = RecoveryRuntime(self.path, self.config, start_workers=False)
        self.assertIsNotNone(self.runtime.app, self.runtime.error)
        self.manager = self.runtime.manager

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def seed(self):
        app = self.runtime.app
        app.store.add_memory("mira", "player-1", "Remember the silver brooch")
        with app.translations.lock, app.translations.db:
            app.translations.db.execute(
                "INSERT INTO preferences VALUES ('player-1',1,'de')"
            )
        return app.salt

    def restore(self, name, scope="all"):
        preview = self.runtime.preview(name, scope)
        return self.runtime.restore(preview["token"], True)

    def test_wal_snapshot_identity_and_restore(self):
        salt = self.seed()
        self.assertTrue((self.path / "roleweaver.sqlite3-wal").exists())
        point = self.runtime.capture()
        self.assertTrue(point["verified"])
        with zipfile.ZipFile(self.manager.path(point["name"])) as z:
            self.assertEqual(z.read("identity_salt").decode(), salt)
            self.assertNotIn(b"NEVER EXPORT THIS", z.read("manifest.json"))
            self.assertEqual(
                set(z.namelist()),
                {*DATABASES.values(), "identity_salt", "manifest.json"},
            )
        self.runtime.app.store.add_memory("mira", "player-1", "Later change")
        self.restore(point["name"])
        self.assertEqual(self.runtime.app.salt, salt)
        self.assertEqual(len(self.runtime.app.store.memories("mira")), 1)
        self.assertEqual(
            self.runtime.app.translations.db.execute(
                "SELECT language FROM preferences"
            ).fetchone()[0],
            "de",
        )
        self.assertTrue(
            list((self.path / "database-quarantine").glob("*/roleweaver.sqlite3"))
        )
        self.assertIn("before-restore", {f["reason"] for f in self.manager.files()})

    def test_translation_only_keeps_new_memories(self):
        self.seed()
        point = self.runtime.capture()
        self.runtime.app.store.add_memory("mira", "player-1", "Keep this newer memory")
        self.restore(point["name"], "translations")
        self.assertEqual(len(self.runtime.app.store.memories("mira")), 2)

    def test_corrupt_world_keeps_recovery_available(self):
        self.seed()
        point = self.runtime.capture()
        self.runtime.close()
        (self.path / "roleweaver.sqlite3").write_bytes(b"broken original data")
        self.runtime = RecoveryRuntime(self.path, self.config, start_workers=False)
        self.manager = self.runtime.manager
        self.assertIsNone(self.runtime.app)
        self.assertFalse(self.runtime.status()["health"]["world"]["ok"])
        self.restore(point["name"])
        self.assertIsNotNone(self.runtime.app)
        originals = list(
            (self.path / "database-quarantine").glob("*/roleweaver.sqlite3")
        )
        self.assertEqual(originals[0].read_bytes(), b"broken original data")

    def test_corrupt_cache_does_not_start_empty_cache(self):
        self.runtime.close()
        (self.path / "translations.sqlite3").write_bytes(b"broken cache")
        self.runtime = RecoveryRuntime(self.path, self.config, start_workers=False)
        self.assertIsNone(self.runtime.app)
        self.assertEqual(
            (self.path / "translations.sqlite3").read_bytes(), b"broken cache"
        )

    def test_missing_world_is_not_new_install(self):
        self.runtime.close()
        (self.path / "roleweaver.sqlite3").unlink()
        self.runtime = RecoveryRuntime(self.path, self.config, start_workers=False)
        self.assertIsNone(self.runtime.app)
        self.assertIn("missing", self.runtime.error)

    def test_bad_archives_rejected_without_changes(self):
        point = self.runtime.capture()
        before = self.runtime.app.salt
        archive = self.path / "bad.zip"
        with zipfile.ZipFile(self.manager.path(point["name"])) as z:
            data = {n: z.read(n) for n in z.namelist()}
        for change in ("checksum", "world", "traversal"):
            copy = dict(data)
            if change == "checksum":
                copy["identity_salt"] = b"a" * 64
            elif change == "world":
                m = json.loads(copy["manifest.json"])
                m["world"] = "other_world"
                copy["manifest.json"] = json.dumps(m).encode()
            else:
                copy["../oops"] = b"no"
            with zipfile.ZipFile(archive, "w") as z:
                for n, b in copy.items():
                    z.writestr(n, b)
            with self.assertRaises(ValueError):
                self.manager.import_archive(archive)
            self.assertEqual(before, self.runtime.app.salt)
        self.assertFalse((self.path.parent / "oops").exists())

    def test_no_space_keeps_existing_recovery(self):
        first = self.runtime.capture()
        with patch.object(
            self.manager, "space", side_effect=ValueError("disk reserve")
        ):
            with self.assertRaises(ValueError):
                self.runtime.capture()
        self.assertEqual([r["name"] for r in self.manager.files()], [first["name"]])

    def test_valid_sqlite_with_invalid_application_data_rolls_back(self):
        db = self.runtime.app.store.db
        original = db.execute("SELECT profile FROM npcs WHERE id='mira'").fetchone()[0]
        with db:
            db.execute("UPDATE npcs SET profile='invalid json' WHERE id='mira'")
        bad = self.runtime.capture()
        with db:
            db.execute("UPDATE npcs SET profile=? WHERE id='mira'", (original,))
        with self.assertRaises(ValueError):
            self.restore(bad["name"])
        self.assertEqual(self.runtime.app.store.get("mira")["name"], "Mira")
        self.assertFalse(self.manager.journal.exists())

    def test_retention_and_protection(self):
        self.manager.configure(
            dict(DEFAULT, keep_recent=2, keep_daily=1, keep_weekly=1)
        )
        manual = self.runtime.capture()
        for _ in range(4):
            self.runtime.capture("scheduled")
        points = self.manager.files()
        self.assertEqual(len(points), 3)
        self.assertIn(manual["name"], {r["name"] for r in points})
        with self.assertRaises(ValueError):
            self.manager.delete(manual["name"])

    def test_live_bridge_and_expired_preview_rejected(self):
        point = self.runtime.capture()
        preview = self.runtime.preview(point["name"], "all")
        self.runtime.app.conversation_hello = dict(seen=time.monotonic())
        with self.assertRaisesRegex(ValueError, "still active"):
            self.runtime.restore(preview["token"], True)
        with self.assertRaises(ValueError):
            self.runtime.restore(preview["token"], True)
        self.assertIsNotNone(self.runtime.app)

    def test_interrupted_swap_rolls_back_original_set(self):
        self.seed()
        point = self.runtime.capture()
        self.runtime.app.store.add_memory("mira", "player-1", "Newer original")
        stage, kinds = self.manager.begin_restore(
            point["name"], "all", self.runtime.app.salt
        )
        self.runtime.app.quiesce()
        q = self.manager.quarantine(kinds)
        self.runtime.app.close()
        self.runtime.app = None
        self.manager.install_restore(stage, kinds, q, "all")
        self.assertTrue(self.manager.rollback_interrupted())
        self.runtime.retry()
        self.assertEqual(len(self.runtime.app.store.memories("mira")), 2)
        import shutil

        shutil.rmtree(stage)

    def test_partial_copy_failure_rolls_back(self):
        self.seed()
        point = self.runtime.capture()
        self.runtime.app.store.add_memory("mira", "player-1", "Newer original")
        real = self.manager.install_restore

        def fail(*args):
            real(*args)
            raise OSError("simulated disk failure")

        with patch.object(self.manager, "install_restore", side_effect=fail):
            with self.assertRaises(OSError):
                self.restore(point["name"])
        self.assertEqual(len(self.runtime.app.store.memories("mira")), 2)
        self.assertFalse(self.manager.journal.exists())

    def test_second_instance_is_rejected(self):
        with self.assertRaises(ValueError):
            InstanceLock(self.path)

    def test_malformed_saved_manifest_does_not_break_recovery_listing(self):
        point = self.runtime.capture()
        with zipfile.ZipFile(self.manager.path(point["name"]), "w") as z:
            z.writestr("manifest.json", "[]")
        self.assertFalse(self.manager.files()[0]["verified"])
        self.assertTrue(self.manager.files()[0]["error"])

    def test_diagnostics_exclude_content_and_identity(self):
        self.seed()
        report = json.dumps(self.runtime.app.translation_diagnostics())
        for private in (
            "silver brooch",
            "player-1",
            self.runtime.app.salt,
            "NEVER EXPORT THIS",
        ):
            self.assertNotIn(private, report)

    def test_restore_drains_http_requests_and_provider_writers(self):
        point = self.runtime.capture()
        release = threading.Event()
        started = threading.Event()
        app = self.runtime.app

        def old_writer():
            started.set()
            release.wait(10)
            app.store.add_memory("mira", "player-1", "Late old result")

        app.pool.submit(old_writer)
        self.assertTrue(started.wait(2))
        preview = self.runtime.preview(point["name"], "all")
        with self.runtime.lease():
            self.runtime.submit(
                "Test restore", lambda: self.runtime.restore(preview["token"], True)
            )
            time.sleep(0.05)
            self.assertTrue(self.runtime.job["running"])
        release.set()
        self.runtime.job_thread.join(10)
        self.assertFalse(self.runtime.job["running"])
        self.assertFalse(self.runtime.job["error"], self.runtime.job["error"])
        self.assertEqual(self.runtime.app.store.memories("mira"), [])


if __name__ == "__main__":
    unittest.main()
