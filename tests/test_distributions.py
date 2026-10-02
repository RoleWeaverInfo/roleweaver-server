"""Release boundaries and no-module bridge preparation."""

import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import subprocess
from unittest.mock import patch
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import package_release
import prepare_addon


class DistributionTests(unittest.TestCase):
    def test_version_mismatch_stops_packaging_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "release.tar.gz"
            with patch.object(package_release, "runtime_version", return_value="0.0.0"):
                with self.assertRaisesRegex(ValueError, "versions must match"):
                    package_release.package(archive)
            self.assertFalse(archive.exists())

    def test_separate_archives_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("demo", "addon"):
                archive = Path(directory) / (kind + ".tar.gz")
                package_release.package(archive, kind)
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertEqual(
                    archive.with_suffix(".gz.sha256").read_text().split()[0], digest
                )
                again = Path(directory) / (kind + "-again.tar.gz")
                package_release.package(again, kind)
                self.assertEqual(archive.read_bytes(), again.read_bytes())
                with tarfile.open(archive) as tar:
                    self.assertEqual(
                        tar.getmember(package_release.NAMES[kind] + "/setup.sh").mode,
                        0o755,
                    )
                    self.assertTrue(
                        all(
                            m.isfile() and ".." not in Path(m.name).parts
                            for m in tar.getmembers()
                        )
                    )
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
                for name, raw in entries.items():
                    if name.endswith((".sh", ".service")):
                        self.assertNotIn(b"\r\n", raw, name)
                release = json.loads(entries["RELEASE.json"])
                self.assertEqual(release["kind"], kind)
                self.assertEqual(release["version"], package_release.VERSION)
                self.assertEqual(release["channel"], "stable")
                self.assertEqual(release["version"], release["runtime_version"])
                self.assertEqual(
                    release["runtime_version"], package_release.runtime_version()
                )
                self.assertIn("RELEASE_NOTES.md", entries)
                self.assertIn("bridge/rw_health.nss", entries)
                self.assertIn("bridge/rw_tr_native.nss", entries)
                self.assertIn("extensions/nwnx_translation/Translation.cpp", entries)
                self.assertIn("setup.sh", entries)
                self.assertIn("tools/setup_wizard.py", entries)
                for helper in (
                    "server_setup",
                    "install_profile",
                    "install_bundle",
                    "manage_installation",
                ):
                    self.assertIn("tools/" + helper + ".py", entries)
                self.assertIn("tools/gff.py", entries)
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
                if kind == "addon":
                    # CLI import smoke check on extracted source, not a server
                    # installation/upgrade rehearsal. No world or service changes.
                    extracted = Path(directory) / "extracted"
                    for name, raw in entries.items():
                        file = extracted / name
                        file.parent.mkdir(parents=True, exist_ok=True)
                        file.write_bytes(raw)
                    for tool in (
                        "setup_wizard.py",
                        "prepare_dialogues.py",
                        "add_translation_guide.py",
                    ):
                        result = subprocess.run(
                            [sys.executable, str(extracted / "tools" / tool), "--help"],
                            cwd=extracted,
                            capture_output=True,
                            text=True,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                    # Import all shipped test modules: missing demo-only helpers
                    # must not break the add-on's standalone developer checks.
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            "import importlib,pathlib,sys; sys.path.insert(0,'tests'); [importlib.import_module('tests.'+p.stem) for p in pathlib.Path('tests').glob('test_*.py')]",
                        ],
                        cwd=extracted,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_and_unreviewed_assets_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(package_release, "ROOT", root):
                for name in (
                    "roleweaver/provider.env",
                    "roleweaver/dashboard-auth.json",
                    "demo/settings.json",
                    "tools/.env.local",
                    "docs/player.sqlite3-wal",
                    "assets/native.so",
                    "assets/other.mod",
                    "roleweaver/data/players.json",
                    "demo/.demo/history.json",
                    "assets/backup.zip",
                    "docs/errors.log",
                    "docs/world-export.json",
                    "examples/saved-translations.json",
                    "demo/results-filled.csv",
                ):
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        package_release.source_file(root / name)
                self.assertFalse(
                    package_release.source_file(root / "tools/__pycache__/test.pyc")
                )

    def test_demo_seed_rejects_runtime_data_in_authored_file(self):
        source = (package_release.ROOT / "demo/content.json").read_text()
        package_release.validate_demo_content(source)
        for field in ("memories", "messages", "translations", "player_identities"):
            data = json.loads(source)
            data[field] = [{"private": "test history"}]
            with self.subTest(field=field), self.assertRaises(ValueError):
                package_release.validate_demo_content(json.dumps(data))
        for field, value in (("memory", "test history"), ("id", "cp_test_owner_pet")):
            data = json.loads(source)
            data["npcs"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                package_release.validate_demo_content(json.dumps(data))
        data = json.loads(source)
        data["encounters"][0]["participants"] = ["test player"]
        with self.assertRaises(ValueError):
            package_release.validate_demo_content(json.dumps(data))

    def test_links_are_checked_against_shipped_files(self):
        contents = {
            "docs/start.md": b"[Guide](../START_HERE.md#setup) [Source](https://example.com) [Directory](../bridge/) [Self](#setup)\n```\n[example](not-a-file.md)\n```",
            "START_HERE.md": b"# Setup",
            "bridge/rw_init.nss": b"void main() {}",
        }
        package_release.validate_document_links(contents)
        del contents["START_HERE.md"]
        with self.assertRaisesRegex(ValueError, "docs/start.md: ../START_HERE.md"):
            package_release.validate_document_links(contents)

    def test_prepared_bridge_contains_all_local_includes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bridge"
            prepare_addon.prepare(
                output, "test_world", "roleweaver:test_world", source_only=True
            )
            scripts = output / "scripts"
            for path in scripts.glob("*.nss"):
                for include in re.findall(r'#include\s+"(rw_[^"]+)"', path.read_text()):
                    self.assertTrue(
                        (scripts / (include + ".nss")).is_file(),
                        f"{path.name}: {include}",
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
