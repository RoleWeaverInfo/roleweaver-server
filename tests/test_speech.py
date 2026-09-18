import unittest

from roleweaver.provider import game_speech


class SpeechTests(unittest.TestCase):
    def test_typographic_punctuation_survives_legacy_encoding(self):
        text = game_speech("\u201cHello again.\u201d It\u2019s warm\u2014come in\u2026")
        self.assertEqual(text, '"Hello again." It\'s warm--come in...')
        self.assertEqual(
            text.encode("latin-1", errors="replace").decode("latin-1"), text
        )

    def test_preserves_real_questions_and_accented_names(self):
        self.assertEqual(
            game_speech('Ren\u00e9: "Are you well?"'), 'Ren\u00e9: "Are you well?"'
        )
