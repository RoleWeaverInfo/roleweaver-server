import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from roleweaver.service import Service
from roleweaver.recovery import RecoveryBackups
from roleweaver import backup


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Service(Path(self.tmp.name), {"provider": "offline"})
        self.r = RecoveryBackups(
            Path(self.tmp.name) / "snapshots",
            self.app.backup_data,
            {"recovery_keep_recent": 2, "recovery_keep_daily": 2},
        )

    def tearDown(self):
        self.app.pool.shutdown(wait=True)
        self.app.store.db.close()
        self.tmp.cleanup()

    def test_snapshot_is_restorable_and_has_identity_and_locations(self):
        self.app.store.message("mira", "player", "player", "Remember me")
        self.app.store.save_placement(
            dict(
                npc="mira",
                world="world",
                session="old",
                area="a",
                area_tag="a",
                tag="mira",
                resref="innkeeper",
                name="Mira",
                source="dm_persistent",
                x=1,
                y=2,
                z=0,
                facing=30,
                dead=0,
            )
        )
        self.assertTrue(self.r.tick(now=1700000000, clock=0))
        data = backup.validate(
            json.loads(self.r.read(self.r.status()["files"][0]["name"]))
        )
        self.assertEqual(data["identity_salt"], self.app.salt)
        self.assertEqual(data["messages"][0]["text"], "Remember me")
        self.assertEqual(data["placements"][0]["x"], 1)
        self.app.restore_data(data)
        self.assertEqual(self.app.store.transcript("mira")[0]["text"], "Remember me")

    def test_schedule_and_rotation_keep_daily_separate(self):
        self.r.tick(now=1700000000, clock=0)
        self.assertFalse(self.r.tick(now=1700000100, clock=100))
        for i in range(1, 5):
            self.assertTrue(self.r.tick(now=1700000000 + i * 86400, clock=i * 86400))
        names = [f["name"] for f in self.r.status()["files"]]
        self.assertEqual(sum(n.startswith("recent-") for n in names), 2)
        self.assertEqual(sum(n.startswith("daily-") for n in names), 2)

    def test_failed_write_preserves_completed_backups_and_reports_error(self):
        self.r.tick(now=1700000000, clock=0)
        before = {p.name: p.read_bytes() for p in self.r.directory.iterdir()}
        with patch(
            "roleweaver.recovery.os.replace", side_effect=OSError("disk unavailable")
        ):
            self.assertFalse(self.r.tick(now=1700000400, clock=400))
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.r.directory.iterdir()}
        )
        self.assertIn("disk unavailable", self.r.status()["error"])
        self.assertTrue(self.r.tick(now=1700000461, clock=461))
        self.assertEqual(self.r.status()["error"], "")

    def test_unrelated_files_are_not_rotated_and_paths_are_rejected(self):
        self.r.directory.mkdir()
        (self.r.directory / "my-manual-backup.json").write_text("keep")
        for i in range(4):
            self.r.tick(now=1700000000 + i * 86400, clock=i * 86400)
        self.assertTrue((self.r.directory / "my-manual-backup.json").exists())
        with self.assertRaises(ValueError):
            self.r.read("../config.json")
        with self.assertRaises(ValueError):
            self.r.read("my-manual-backup.json")

    def test_disabled_creates_nothing(self):
        self.r.enabled = False
        self.assertFalse(self.r.tick())
        self.assertFalse(self.r.directory.exists())

    def test_restart_keeps_existing_daily_snapshot(self):
        self.r.tick(now=1700000000, clock=0)
        daily = next(self.r.directory.glob("daily-*.json"))
        original = daily.read_bytes()
        self.app.save_world_lore("Changed")
        other = RecoveryBackups(self.r.directory, self.app.backup_data, {})
        other.tick(now=1700000100, clock=0)
        self.assertEqual(daily.read_bytes(), original)
