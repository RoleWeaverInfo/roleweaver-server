"""Run from the repository root: python demo/investigation/test_content.py."""

import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from roleweaver.store import Store, DEFAULT_NPC
from roleweaver.authoring import visible_lore
from seed import seed


class InvestigationTests(unittest.TestCase):
    def test_seed_preserves_memory_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as t:
            db = Path(t) / "test.db"
            s = Store(db)
            for id in ("tavern_owner", "merchant_one"):
                s.save(dict(DEFAULT_NPC, id=id, name=id))
            s.add_memory("tavern_owner", "test_player", "Player prefers tea.")
            s.db.close()
            content = Path(__file__).with_name("content.json")
            seed(db, content, "my_world")
            seed(db, content, "my_world")
            s = Store(db)
            self.assertEqual(len(s.list_npcs()), 8)
            self.assertEqual(len(s.memories("tavern_owner", "test_player")), 1)
            self.assertEqual(len(s.world_documents()), 6)
            self.assertEqual(len(s.access_lore()), 9)
            config = json.loads(
                s.db.execute(
                    "SELECT value FROM backup_settings WHERE key='controlled_actions'"
                ).fetchone()[0]
            )
            self.assertEqual(len(config["destinations"]), 7)
            self.assertFalse(config["npcs"]["tavern_owner"]["shop"])
            s.db.close()

    def test_refresh_and_reset_preserve_authoring_and_other_npcs(self):
        from refresh_content import refresh

        with tempfile.TemporaryDirectory() as t:
            db = Path(t) / "test.db"
            s = Store(db)
            for ident in ("tavern_owner", "merchant_one", "outside_demo"):
                s.save(dict(DEFAULT_NPC, id=ident, name=ident))
            s.db.close()
            content = Path(__file__).with_name("content.json")
            seed(db, content, "my_world")
            s = Store(db)
            profile = s.get("tavern_owner")
            profile.update(name="Custom innkeeper", mode="paused", appearance="211")
            s.save(profile)
            s.message("tavern_owner", "tester", "player", "The culprit was Holt.")
            s.add_memory("tavern_owner", "tester", "The investigation was completed.")
            s.add_memory("tavern_owner", "", "DM-authored shared background.")
            s.message("outside_demo", "tester", "player", "Keep this conversation.")
            with s.db:
                s.db.execute(
                    "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                    ("merchant_configs", '{"keep":"stock policy"}'),
                )
            settings = list(s.db.execute("SELECT * FROM backup_settings ORDER BY key"))
            settings = [tuple(x) for x in settings]
            doc = s.world_documents()[0]
            doc["active"] = False
            s.save_world_document(doc)
            s.db.close()
            refresh(db, content)
            s = Store(db)
            self.assertEqual(len(s.transcript("tavern_owner")), 1)
            s.db.close()
            counts = refresh(db, content, True)
            self.assertEqual(counts, dict(messages=1, player_memories=1))
            s = Store(db)
            self.assertEqual(s.get("tavern_owner")["name"], "Custom innkeeper")
            self.assertEqual(s.get("tavern_owner")["mode"], "paused")
            self.assertEqual(s.get("tavern_owner")["appearance"], "211")
            self.assertEqual(len(s.transcript("outside_demo")), 1)
            self.assertEqual(len(s.memories("tavern_owner")), 1)
            self.assertEqual(
                [
                    tuple(x)
                    for x in s.db.execute("SELECT * FROM backup_settings ORDER BY key")
                ],
                settings,
            )
            self.assertFalse(
                next(d for d in s.world_documents() if d["id"] == doc["id"])["active"]
            )
            s.db.close()

    def test_lore_copies_match_and_no_shared_solution(self):
        c = json.loads(Path(__file__).with_name("content.json").read_text())
        for d in c["world_documents"] + c["access_lore"]:
            self.assertEqual(
                (Path(__file__).with_name("lore") / (d["id"] + ".md")).read_text(
                    encoding="utf-8"
                ),
                "# " + d["title"] + "\n\n" + d["text"] + "\n",
            )
        for d in c["access_lore"]:
            if d["target"] != "rq_holt":
                self.assertNotIn("Holt intentionally denies", d["disclosure"])
        from roleweaver.lore_documents import validate_documents

        validate_documents(c["world_documents"])

    def test_session_wrappers_preserve_existing_hooks(self):
        from session_hooks import install
        from build import node

        module = node(
            [
                ("Mod_OnClientEntr", (11, b"world_enter")),
                ("Mod_OnClientLeav", (11, b"world_exit")),
            ]
        )
        install(module)
        install(module)
        self.assertEqual(module[1]["Mod_OnClientEntr"][1], b"rq_enter")
        self.assertEqual(module[1]["Mod_OnClientLeav"][1], b"rq_exit")
        variables = {
            v[1]["Name"][1]: v[1]["Value"][1] for v in module[1]["VarTable"][1]
        }
        self.assertEqual(
            variables,
            {b"rq_previous_enter": b"world_enter", b"rq_previous_exit": b"world_exit"},
        )

    def test_restore_merges_history_without_replacing_new_conversations(self):
        from restore_history import restore

        with tempfile.TemporaryDirectory() as t:
            old = Path(t) / "old.db"
            live = Path(t) / "live.db"
            for path in (old, live):
                store = Store(path)
                store.save(dict(DEFAULT_NPC, id="tavern_owner", name="Host"))
                store.db.close()
            store = Store(old)
            store.message("tavern_owner", "p", "player", "My name is Ari.")
            store.add_memory("tavern_owner", "p", "Ari likes tea.")
            store.db.close()
            store = Store(live)
            store.message("tavern_owner", "p", "player", "A new visit.")
            store.db.close()
            self.assertEqual(restore(live, old), dict(messages=1, memories=1))
            self.assertEqual(restore(live, old), dict(messages=0, memories=0))
            store = Store(live)
            self.assertEqual(
                [row["text"] for row in store.transcript("tavern_owner")],
                ["My name is Ari.", "A new visit."],
            )
            self.assertEqual(len(store.memories("tavern_owner", "p")), 1)
            store.db.close()

    def test_private_evidence_is_scoped(self):
        c = json.loads(Path(__file__).with_name("content.json").read_text())
        wizard = next(p for p in c["profiles"] if p["id"] == "rq_wizard")
        titles = [d["title"] for d in visible_lore(c["access_lore"], wizard)]
        self.assertEqual(len(titles), 2)
        self.assertFalse(any("Meriel" in x or "Holt" in x for x in titles))
        public = " ".join(d["text"] for d in c["world_documents"])
        self.assertNotIn("Holt arranged", public)


if __name__ == "__main__":
    unittest.main()
