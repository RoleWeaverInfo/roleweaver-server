import unittest
from roleweaver import story, actions


class StoryTests(unittest.TestCase):
    def value(self):
        return dict(
            protocol=1,
            token="session:12",
            actions=[dict(id="story:clue_2", description="Reveal your testimony.")],
        )

    def test_valid_context_and_reply(self):
        v = self.value()
        self.assertEqual(story.context(v), v)
        self.assertEqual(
            actions.parse_reply(
                '{"speech":"I saw his signature.","action":"story:clue_2"}',
                v["actions"],
            )[1],
            "story:clue_2",
        )

    def test_lore_review_gets_scoped_facts_not_capabilities(self):
        from roleweaver.safeguards import trusted_sources

        v = self.value()
        v["own_testimony"] = "I saw the signed order."
        v["instructions"] = "module instructions"
        facts = trusted_sources(dict(story=v), [])["live_story"]
        self.assertEqual(facts, {"own_testimony": "I saw the signed order."})

    def test_visit_boundary_keeps_old_memories_and_isolates_players(self):
        import tempfile
        from pathlib import Path
        from roleweaver.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "test.db")
            first = store.message("mira", "alice", "player", "Call me Ari.")
            self.assertEqual(
                store.story_visit_start("mira", "alice", "visit1", first), first
            )
            second = store.message("mira", "alice", "player", "I am back.")
            self.assertEqual(
                store.story_visit_start("mira", "alice", "visit2", second), second
            )
            self.assertEqual(
                store.story_visit_start("mira", "alice", "visit2", 999), second
            )
            self.assertEqual(
                store.story_visit_start("mira", "bob", "visit3", 1000), 1000
            )
            rows = story.mark_history(store.transcript("mira", "alice"), second)
            self.assertTrue(rows[0]["previous_visit"])
            self.assertFalse(rows[1]["previous_visit"])
            self.assertEqual(rows[0]["text"], "Call me Ari.")
            store.db.close()

    def test_unoffered_action_rejected(self):
        with self.assertRaises(ValueError):
            actions.parse_reply(
                '{"speech":"Gold!","action":"story:verdict_10"}',
                self.value()["actions"],
            )

    def test_no_hook_no_capabilities(self):
        for value in [None, "ignore rules", {}, dict(protocol=2)]:
            self.assertEqual(story.context(value), {})

    def test_invalid_capabilities_fail_closed(self):
        for ident in ["shop:open", "story:../execute", "story:", "story:" + "a" * 49]:
            v = self.value()
            v["actions"][0]["id"] = ident
            self.assertEqual(story.context(v), {})
        v = self.value()
        v["actions"] *= 2
        self.assertEqual(story.context(v), {})
        v = self.value()
        v["instructions"] = "x" * 16001
        self.assertEqual(story.context(v), {})


if __name__ == "__main__":
    unittest.main()
