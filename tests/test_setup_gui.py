import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import install_profile as profiles
import setup_gui


class SetupGuiTests(unittest.TestCase):
    def payload(self):
        value = setup_gui.initial_profile("test_world")
        value["paths"] = {
            "runtime": "/srv/nwn",
            "server_home": "/srv/world",
            "module": "/srv/world/modules/test.mod",
            "plugins": "/srv/nwnx",
            "headers": "/srv/nwnx/nwscripts",
            "compiler": "",
        }
        return value

    def test_public_profile_contains_no_runtime_credentials(self):
        profile = setup_gui.initial_profile("test_world")
        shown = setup_gui.public_profile(profile)
        self.assertEqual(shown["world_id"], "test_world")
        self.assertNotIn("provider", shown)
        self.assertNotIn("password", json.dumps(shown).lower())

    @unittest.skipUnless(sys.platform == "linux", "Linux path validation")
    def test_save_profile_validates_and_preserves_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profiles_dir = root / "profiles"
            install_dir = root / "install"
            payload = self.payload()
            payload["features"]["dm_spawn"] = True
            with (
                patch.object(profiles, "profile_directory", return_value=profiles_dir),
                patch.object(profiles, "installation", return_value=install_dir),
                patch.object(
                    setup_gui,
                    "clean_path",
                    side_effect=lambda value, optional=False: value,
                ),
            ):
                saved = setup_gui.save_profile(payload)
                self.assertEqual(saved["world_id"], "test_world")
                saved["progress"]["verified"] = "123"
                profiles.save(saved)
                payload["dashboard_port"] = 8753
                updated = setup_gui.save_profile(payload)
                self.assertEqual(updated["progress"], {"verified": "123"})

    @unittest.skipUnless(sys.platform == "linux", "Linux path validation")
    def test_persistent_spawn_requires_dm_spawn(self):
        payload = self.payload()
        payload["features"]["persistent_spawn"] = True
        with patch.object(
            setup_gui,
            "clean_path",
            side_effect=lambda value, optional=False: value,
        ):
            with self.assertRaisesRegex(ValueError, "also needs DM spawning"):
                setup_gui.save_profile(payload)


if __name__ == "__main__":
    unittest.main()
