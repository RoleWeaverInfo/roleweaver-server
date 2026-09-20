"""Release boundaries and no-module bridge preparation."""

import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import package_release
import prepare_addon


class DistributionTests(unittest.TestCase):
    def test_separate_archives_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("demo", "addon"):
                archive = Path(directory) / (kind + ".tar.gz")
                package_release.package(archive, kind)
                with tarfile.open(archive) as tar:
                    entries = {
                        m.name.split("/", 1)[1]: tar.extractfile(m).read()
                        for m in tar.getmembers()
                    }
                manifest = json.loads(entries.pop("MANIFEST.sha256.json"))
                self.assertEqual(
                    manifest,
                    {n: hashlib.sha256(b).hexdigest() for n, b in entries.items()},
                )
                self.assertIn("START_HERE.md", entries)
                self.assertIn("roleweaver/static/rw_server_splash.png", entries)
                module_path = (
                    "demo/world/YourWorld_Fixed.mod"
                    if kind == "demo"
                    else "addon/example-world/YourWorld_Fixed.mod"
                )
                self.assertEqual(
                    entries[module_path],
                    (
                        package_release.ROOT / "demo/world/YourWorld_Fixed.mod"
                    ).read_bytes(),
                )
                self.assertEqual(
                    [n for n in entries if n.endswith(".mod")], [module_path]
                )
                self.assertEqual(
                    any(n.startswith("demo/") for n in entries), kind == "demo"
                )

    def test_source_only_needs_no_world_or_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bridge"
            manifest = prepare_addon.prepare(
                output, "test_world", "roleweaver:test_world", source_only=True
            )
            self.assertFalse(manifest["compiled"])
            self.assertFalse((output / "scripts/rw_load.nss").exists())
            self.assertNotIn(
                "NWNX_Chat_RegisterChatScript",
                (output / "scripts/rw_init.nss").read_text(),
            )
            config = json.loads((output / "service-config.example.json").read_text())
            self.assertEqual(config["placement_owner"], "world")
            self.assertFalse(config["allow_dm_spawn"])
            for name, digest in manifest["files"].items():
                self.assertEqual(
                    hashlib.sha256((output / name).read_bytes()).hexdigest(), digest
                )
            with self.assertRaises(ValueError):
                prepare_addon.prepare(
                    output, "test_world", "roleweaver:test_world", source_only=True
                )

    def test_missing_dependencies_do_not_create_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bridge"
            with self.assertRaises(ValueError):
                prepare_addon.prepare(output, "test_world", "roleweaver:test_world")
            self.assertFalse(output.exists())

    def test_invalid_namespace_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                prepare_addon.prepare(
                    Path(directory) / "bridge",
                    "bad/world",
                    "roleweaver:test",
                    source_only=True,
                )
