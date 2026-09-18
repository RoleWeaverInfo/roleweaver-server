import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from roleweaver import backup, safeguards
from roleweaver.store import Store
from roleweaver.service import Service


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def doc(self, id="history", active=True, text="The village was founded by Elira."):
        return dict(id=id, title=id.title(), text=text, active=active)

    def test_migrates_old_lore_once_without_resurrecting_deleted_document(self):
        self.store.db.close()
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM metadata WHERE key='world_documents_migrated'")
            db.execute("INSERT INTO world_lore VALUES (1,?)", ("Existing lore",))
        db.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.world_lore(), "Existing lore")
        self.assertTrue(self.store.world_documents()[0]["active"])
        self.store.delete_world_document("world_lore")
        self.store.db.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.world_documents(), [])

    def test_only_active_documents_reach_prompts_and_reviews(self):
        self.store.save_world_document(self.doc())
        self.store.save_world_document(
            self.doc("inactive", False, "INACTIVE WORLD FACT")
        )
        self.assertNotIn("INACTIVE", self.store.world_lore())
        profile = dict(self.store.get("mira"), world_lore=self.store.world_lore())
        self.assertNotIn("INACTIVE", str(safeguards.trusted_sources(profile, [])))
        self.store.toggle_world_document("inactive", True)
        self.assertIn("INACTIVE", self.store.world_lore())
        self.store.toggle_world_document("history", False)
        self.assertEqual(len(self.store.world_documents()), 2)
        self.assertNotIn("Elira", self.store.world_lore())

    def test_editing_does_not_reactivate_documents_or_entries(self):
        doc = self.doc(active=False)
        self.store.save_world_document(doc)
        doc.pop("active")
        doc["text"] = "Changed"
        self.assertFalse(self.store.save_world_document(doc)["active"])
        entry = dict(
            id="local", title="Local", text="Fact", audience="public", active=False
        )
        self.store.save_access_lore(entry)
        entry.pop("active")
        entry["text"] = "Changed"
        self.assertFalse(self.store.save_access_lore(entry)["active"])
        self.assertEqual(self.store.lore_for(self.store.get("mira")), [])

    def test_access_switch_never_bypasses_audience(self):
        for id, audience, active in [
            ("public", "public", False),
            ("private", "dm", True),
        ]:
            self.store.save_access_lore(
                dict(id=id, title=id, text=id, audience=audience, active=active)
            )
        self.assertEqual(self.store.lore_for(self.store.get("mira")), [])
        self.store.toggle_access_lore("public", True)
        self.assertEqual(
            [e["title"] for e in self.store.lore_for(self.store.get("mira"))],
            ["public"],
        )
        self.store.toggle_access_lore("private", False)
        self.store.toggle_access_lore("private", True)
        self.assertEqual(len(self.store.lore_for(self.store.get("mira"))), 1)

    def test_active_budget_rejection_is_atomic(self):
        self.store.save_world_document(self.doc(text="a" * 19000))
        self.store.save_world_document(self.doc("other", False, "b" * 2000))
        with self.assertRaises(ValueError):
            self.store.toggle_world_document("other", True)
        self.assertFalse(
            next(d for d in self.store.world_documents() if d["id"] == "other")[
                "active"
            ]
        )
        self.assertEqual(self.store.world_lore(), "a" * 19000)
        with self.assertRaises(ValueError):
            self.store.save_world_document(self.doc(text="a" * 20001))

    def test_backup_preserves_inactive_sources_and_old_format_migrates(self):
        self.store.save_world_document(self.doc(active=False))
        self.store.save_access_lore(
            dict(
                id="entry", title="Entry", text="Lore", audience="public", active=False
            )
        )
        data = backup.validate(backup.export(self.store, "a" * 64))
        backup.replace(self.store, data)
        self.assertFalse(self.store.world_documents()[0]["active"])
        self.assertFalse(self.store.access_lore()[0]["active"])
        self.assertEqual(self.store.world_lore(), "")
        old = backup.export(self.store, "a" * 64)
        old["version"] = 4
        old.pop("world_documents")
        old["world_lore"] = "Legacy facts"
        old["access_lore"][0].pop("active")
        clean = backup.validate(old)
        backup.replace(self.store, clean)
        self.assertEqual(self.store.world_lore(), "Legacy facts")
        self.assertTrue(self.store.access_lore()[0]["active"])

    def test_invalid_flags_ids_and_duplicate_backup_documents(self):
        for value in ("false", 0, None):
            with self.assertRaises(ValueError):
                self.store.save_world_document(self.doc(active=value))
        with self.assertRaises(ValueError):
            self.store.toggle_access_lore("missing", True)
        data = backup.export(self.store, "a" * 64)
        data["world_documents"] = [self.doc(), self.doc()]
        with self.assertRaises(ValueError):
            backup.validate(data)

    def test_inactive_lore_not_sent_by_service(self):
        app = Service(Path(self.temp.name) / "app", {"provider": "offline"})
        try:
            app.store.save_world_document(self.doc("off", False, "NEVER SUPPLY WORLD"))
            app.store.save_access_lore(
                dict(
                    id="off",
                    title="Off",
                    text="NEVER SUPPLY ACCESS",
                    audience="public",
                    active=False,
                )
            )
            app.event(
                dict(
                    kind="state",
                    npc="mira",
                    session="test",
                    epoch=1,
                    tick=1,
                    mode="auto",
                    object="a",
                )
            )
            with patch.object(app.pool, "submit") as submit:
                app.event(
                    dict(
                        kind="chat",
                        npc="mira",
                        session="test",
                        epoch=1,
                        event_id="one",
                        player="key:Test",
                        text="Hello",
                        speech_format=1,
                    )
                )
                profile = submit.call_args.args[3]
                self.assertEqual(profile["world_lore"], "")
                self.assertEqual(profile["access_lore"], [])
        finally:
            app.pool.shutdown()
            app.store.db.close()
