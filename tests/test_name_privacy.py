import unittest
from roleweaver.provider import private_transcript


class NamePrivacyTests(unittest.TestCase):
    def test_legacy_labels_and_ungrounded_reply_do_not_teach_name(self):
        rows = [
            dict(speaker="player", text="Aluvian Darkstar: Hello.", created=1),
            dict(speaker="npc", text="Greetings, Aluvian!", created=2),
            dict(speaker="npc", text="Welcome to the inn.", created=3),
        ]
        clean = private_transcript(rows, "Aluvian Darkstar", 10)
        self.assertEqual([r["text"] for r in clean], ["Hello.", "Welcome to the inn."])
        self.assertEqual(rows[0]["text"], "Aluvian Darkstar: Hello.")

    def test_introductions_and_aliases_are_preserved(self):
        rows = [
            dict(speaker="player", text="Aluvian Darkstar: Call me Raven.", created=1),
            dict(
                speaker="player",
                text="Aluvian Darkstar: My name is Aluvian.",
                created=2,
            ),
        ]
        clean = private_transcript(rows, "Aluvian Darkstar", 10)
        self.assertEqual(
            [r["text"] for r in clean], ["Call me Raven.", "My name is Aluvian."]
        )

    def test_new_conversations_are_not_rewritten(self):
        rows = [
            dict(speaker="player", text="My name is Aluvian.", created=11),
            dict(speaker="npc", text="Well met, Aluvian.", created=12),
        ]
        self.assertEqual(private_transcript(rows, "Aluvian Darkstar", 10), rows)
