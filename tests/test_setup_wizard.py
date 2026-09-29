"""Validate setup paths/links without installing or restarting any service."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import setup_wizard as wizard


class WizardTests(unittest.TestCase):
    def test_validated_input_and_numbered_output(self):
        for value in ("../world", "bad;command", "Uppercase"):
            with self.assertRaises(ValueError):
                wizard.identifier(value)
        with self.assertRaises(ValueError):
            wizard.port("0")
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(wizard, "ROOT", Path(folder)),
        ):
            first = wizard.next_output("world-import")
            first.mkdir(parents=True)
            self.assertNotEqual(first, wizard.next_output("world-import"))
            self.assertTrue(first.exists())

    @unittest.skipUnless(sys.platform == "linux", "Linux directory symlinks")
    def test_existing_dependency_link_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime = root / "runtime"
            plugins = root / "plugins"
            headers = root / "headers"
            (runtime / "bin/linux-x86").mkdir(parents=True)
            (runtime / "data").mkdir()
            (runtime / "data/game.key").touch()
            (runtime / "data/game.bif").touch()
            exe = runtime / "bin/linux-x86/nwserver-linux"
            exe.write_text("test")
            exe.chmod(0o700)
            plugins.mkdir()
            headers.mkdir()
            for name in wizard.PLUGINS:
                (plugins / f"NWNX_{name}.so").touch()
            with patch.object(wizard, "required_headers"):
                destination = root / "links"
                wizard.native_links(destination, runtime, plugins, headers)
                wizard.native_links(destination, runtime, plugins, headers)
                another = root / "another"
                another.mkdir()
                with self.assertRaises(ValueError):
                    wizard.native_links(destination, runtime, plugins, another)
            self.assertEqual((destination / "nwscripts").resolve(), headers.resolve())


if __name__ == "__main__":
    unittest.main()
