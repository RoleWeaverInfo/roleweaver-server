"""Focused checks for read-only, content-free translation diagnostics."""

import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from roleweaver.service import Service
from roleweaver.translation import DEFAULT


class TranslationDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Service(Path(self.temp.name), dict(provider="offline"))
        self.cache = self.app.translations
        self.cache.configure(dict(DEFAULT, enabled=True, per_minute=1))

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_active_rate_wait_and_content_free_export(self):
        self.cache.lookup("PRIVATE_PLAYER", "fr", "name", "SECRET source")
        self.cache.lookup("PRIVATE_PLAYER", "es", "name", "SECRET source")
        active = []

        def translate(row):
            active.append(self.app.translation_diagnostics()["active_seconds"])
            return "SECRET translation"

        self.cache.process_one(translate)
        with patch(
            "roleweaver.provider.open_url",
            side_effect=AssertionError("Must not call an LLM"),
        ):
            result = self.app.translation_diagnostics()
        self.assertIsNotNone(active[0])
        self.assertIsNone(result["active_seconds"])
        self.assertGreater(result["rate_wait_seconds"], 0)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["by_language"]["fr"]["ready"], 1)
        self.assertEqual(result["last_job"]["status"], "ready")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("PRIVATE_PLAYER", json.dumps(result))

    def test_failure_has_safe_category_without_private_error_text(self):
        self.cache.lookup("identity", "fr", "name", "Chest")

        def fail(row):
            raise TimeoutError("sk-private-key PRIVATE provider reply")

        self.cache.process_one(fail)
        result = self.app.translation_diagnostics()
        self.assertEqual(result["last_job"]["error"], "TimeoutError")
        self.assertIsNone(result["active_seconds"])
        self.assertNotIn("private", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
