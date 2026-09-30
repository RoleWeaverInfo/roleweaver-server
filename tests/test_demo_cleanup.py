"""Demo pruning must keep memories and restore references consistently."""

import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from demo import cleanup, demo
from roleweaver.store import Store, DEFAULT_NPC
from roleweaver.recovery_runtime import InstanceLock


class DemoCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "data"
        self.directory.mkdir()
        self.content = demo.content(demo.ROOT / "demo/content.json")
        self.path = self.directory / "roleweaver.sqlite3"
        demo.seed_database(self.path, self.content, "test_world")
        self.store = Store(self.path)
        self.store.save(dict(DEFAULT_NPC, id="old_spider", name="Old test spider"))
        self.store.message("old_spider", "test_player", "player", "obsolete test")
        self.store.add_memory("old_spider", "test_player", "obsolete memory")
        self.store.message("morga", "test_player", "player", "I remember our meeting.")
        self.store.add_memory("morga", "test_player", "We met before.")
        self.store.save_world_document(
            dict(id="obsolete", title="Old test", text="Old", active=True)
        )
        old = copy.deepcopy(self.content["access_lore"][0])
        old.update(id="old_spider_lore", target="old_spider")
        self.store.save_access_lore(old)
        row = self.store.db.execute(
            "SELECT value FROM backup_settings WHERE key='encounters'"
        ).fetchone()
        data = json.loads(row[0])
        old = copy.deepcopy(next(iter(data["templates"].values())))
        old.update(
            id="old_scene",
            actors=[dict(npc="old_spider", role="test", knowledge="", goal="")],
        )
        data["templates"]["old_scene"] = old
        with self.store.db:
            self.store.db.execute("UPDATE messages SET created=1")
            self.store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES ('encounters',?)",
                (json.dumps(data),),
            )
            self.store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES ('live_encounter_journal',?)",
                (json.dumps({"old": {"run": {"status": "expired"}}}),),
            )

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_prunes_old_cast_and_scenes_but_keeps_conversation_memory(self):
        self.assertTrue(self.store.dashboard_transcript("morga"))
        report = cleanup.prune(self.store, self.content, "test_world", now=2)
        self.assertEqual(report["removed_npcs"], ["old_spider"])
        self.assertEqual(report["encounters"], ["forest_robbery", "troll_ransom"])
        self.assertFalse(self.store.dashboard_transcript("morga"))
        self.assertEqual(len(self.store.transcript("morga", "test_player")), 1)
        self.assertEqual(len(self.store.memories("morga", "test_player")), 1)
        self.assertFalse(self.store.transcript("old_spider"))
        self.assertFalse(self.store.memories("old_spider"))
        self.assertEqual(report["removed_documents"], ["obsolete"])
        self.assertEqual(report["removed_lore"], ["old_spider_lore"])
        self.store.message("morga", "test_player", "npc", "Welcome back.")
        self.assertEqual(
            [m["text"] for m in self.store.dashboard_transcript("morga")],
            ["Welcome back."],
        )
        self.assertEqual(len(self.store.transcript("morga", "test_player")), 2)
        scenes = json.loads(
            self.store.db.execute(
                "SELECT value FROM backup_settings WHERE key='encounters'"
            ).fetchone()[0]
        )
        self.assertTrue(
            all(
                r["status"] == "waiting"
                and r["stage"] == r["template"]["stages"][0]["id"]
                for r in scenes["runs"].values()
            )
        )
        self.assertEqual(len(scenes["templates"]), 2)

    def test_preview_does_not_change_data_and_apply_backs_up_usage(self):
        self.store.db.close()
        usage = self.directory / "usage.sqlite3"
        with closing(sqlite3.connect(usage)) as db, db:
            db.executescript(
                "CREATE TABLE requests (id INTEGER); INSERT INTO requests VALUES (1); CREATE TABLE prices (model TEXT); INSERT INTO prices VALUES ('saved_rate');"
            )
        logs = self.directory / "logs"
        logs.mkdir()
        (logs / "errors.jsonl").write_text('{"event":"old"}\n')
        report = cleanup.clean(self.directory, self.content, "test_world")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM npcs WHERE id='old_spider'"
                ).fetchone()[0],
                1,
            )
        with InstanceLock(self.directory):
            with self.assertRaisesRegex(ValueError, "Another Role Weaver process"):
                cleanup.clean(self.directory, self.content, "test_world", apply=True)
        applied = cleanup.clean(self.directory, self.content, "test_world", apply=True)
        self.assertEqual(report["removed_npcs"], applied["removed_npcs"])
        recovery = Path(applied["backup"])
        with closing(sqlite3.connect(recovery / "roleweaver.sqlite3")) as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM npcs WHERE id='old_spider'"
                ).fetchone()[0],
                1,
            )
        with closing(sqlite3.connect(usage)) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM requests").fetchone()[0], 0
            )
            self.assertEqual(
                db.execute("SELECT model FROM prices").fetchone()[0], "saved_rate"
            )
        self.assertTrue((recovery / "logs/errors.jsonl").is_file())
        self.assertFalse((logs / "errors.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
