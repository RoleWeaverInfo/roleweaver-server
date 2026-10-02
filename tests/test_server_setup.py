"""Existing-world setup, safe preparation and software recovery regressions."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import install_profile as profiles
import install_bundle as bundles
import manage_installation as manager
import server_setup
from setup_addon import HEADERS


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        paths = {k: (self.root / k).as_posix() for k in profiles.PATHS}
        paths["compiler"] = ""
        paths["module"] = (self.root / "server_home/modules/World.mod").as_posix()
        for name in (
            "headers",
            "plugins",
            "runtime/data",
            "runtime/bin/linux-x86",
            "server_home/modules",
        ):
            (self.root / name).mkdir(parents=True)
        for name in HEADERS:
            (self.root / "headers" / f"nwnx_{name}.nss").write_text(
                "// matching headers\n"
            )
        for name in profiles.PLUGINS:
            (self.root / "plugins" / f"NWNX_{name}.so").touch()
        (self.root / "runtime/data/game.key").touch()
        (self.root / "runtime/data/game.bif").touch()
        (self.root / "runtime/bin/linux-x86/nwserver-linux").touch()
        Path(paths["module"]).write_bytes(b"untouched module")
        self.p = dict(
            version=1,
            world_id="test_world",
            redis_prefix="roleweaver:test_world",
            redis_port=6379,
            dashboard_port=18748,
            paths=paths,
            resources=[],
            features=dict.fromkeys(profiles.FEATURES, False),
            progress={},
        )
        self.patch(profiles, "profile_directory", lambda: self.root / "profiles")
        self.patch(
            profiles, "installation", lambda world: self.root / "installed" / world
        )

    def patch(self, obj, name, value):
        return self.enterContext(patch.object(obj, name, value))

    def test_profile_survives_new_download_and_rejects_unsafe_values(self):
        profiles.save(self.p)
        with patch.object(profiles, "ROOT", self.root / "another-download"):
            self.assertEqual(profiles.load("test_world"), self.p)
        for key, bad in (
            ("world_id", "../another"),
            ("redis_port", True),
            ("redis_prefix", "line\nbreak"),
        ):
            with self.assertRaises(ValueError):
                profiles.validate(dict(self.p, **{key: bad}))
        bad = copy.deepcopy(self.p)
        bad["features"]["persistent_spawn"] = True
        with self.assertRaises(ValueError):
            profiles.save(bad)
        self.assertEqual(profiles.load("test_world"), self.p)

    def test_existing_identity_cannot_be_changed_by_upgrade(self):
        root = profiles.installation("test_world")
        root.mkdir(parents=True)
        (root / "config.json").write_text(
            json.dumps(
                dict(
                    world_id="test_world",
                    redis_prefix="existing",
                    web_port=18748,
                    redis_port=6379,
                )
            )
        )
        with self.assertRaisesRegex(ValueError, "do not match"):
            profiles.installed_settings(self.p)

    def test_checks_detect_missing_headers_and_keep_server_untouched(self):
        original = Path(self.p["paths"]["module"]).read_bytes()
        (self.root / "headers/nwnx_item.nss").unlink()
        rows = profiles.checks(self.p, network=False)
        self.assertTrue(
            any(r["name"] == "NWNX includes" and r["status"] == "fix" for r in rows)
        )
        self.assertTrue(
            any(r["name"] == "Compiler" and r["status"] == "review" for r in rows)
        )
        self.assertEqual(Path(self.p["paths"]["module"]).read_bytes(), original)
        self.assertFalse(profiles.installation("test_world").exists())

    def test_no_installation_cannot_verify_an_unrelated_dashboard(self):
        with patch.object(server_setup.urllib.request, "urlopen") as request:
            self.assertFalse(server_setup.verify(self.p))
        request.assert_not_called()

    def test_translation_uses_profile_without_writing_legacy_settings(self):
        with (
            patch.object(bundles, "current", return_value=True),
            patch.object(server_setup.ui, "dialogues") as dialogues,
        ):

            def observe():
                self.assertEqual(server_setup.ui.SAVED_INSTALLATION, self.p)

            dialogues.side_effect = observe
            server_setup.translation(self.p, "dialogues")
        self.assertIsNone(server_setup.ui.SAVED_INSTALLATION)

    @unittest.skipUnless(sys.platform == "linux", "Linux proc links")
    def test_detection_excludes_passwords_and_other_environment(self):
        process = self.root / "proc/123"
        process.mkdir(parents=True)
        (process / "exe").symlink_to(self.root / "runtime/bin/linux-x86/nwserver-linux")
        (process / "cmdline").write_bytes(
            b"nwserver-linux\0-userdirectory\0/world\0-module\0World\0-dmpassword\0private-password\0"
        )
        (process / "environ").write_bytes(
            b"NWNX_CORE_LOAD_PATH=/plugins\0ROLEWEAVER_API_KEY=secret-key\0"
        )
        value = profiles.discover(self.root / "proc")
        self.assertEqual(value[0]["module"], "/world/modules/World.mod")
        self.assertNotIn("private-password", json.dumps(value))
        self.assertNotIn("secret-key", json.dumps(value))


class BundleTests(unittest.TestCase):
    setUp = ProfileTests.setUp
    patch = ProfileTests.patch

    def test_preparation_preserves_module_and_builds_reviewable_import(self):
        original = Path(self.p["paths"]["module"]).read_bytes()
        self.p["features"].update(dm_spawn=True, persistent_spawn=True)
        real_root = profiles.ROOT
        (self.root / "package/addon").mkdir(parents=True)
        (self.root / "package/addon/AURORA.md").write_bytes(
            (real_root / "addon/AURORA.md").read_bytes()
        )
        report = dict(
            module_hooks={
                "Mod_OnModLoad": "customload",
                "Mod_OnPlrChat": "privatechat",
            },
            reserved_resource_collisions=["rw_init"],
            possible_chat_registrations=["privatechat"],
            scripts_inspected=1,
        )
        with (
            patch.object(bundles, "audit", return_value=report),
            patch.object(profiles, "ROOT", self.root / "package"),
            patch.object(profiles, "signature", return_value="test-signature"),
        ):
            out = bundles.prepare(self.p)
            self.assertTrue(bundles.current(self.p))
            self.assertEqual(
                (out / "RoleWeaver-Import.erf").read_bytes()[:8], b"ERF V1.0"
            )
            self.assertIn(
                '"rw_allow_persistent_spawn", TRUE',
                (out / "scripts/rw_userload.nss").read_text(),
            )
            self.assertIn("privatechat", (out / "INSTALL.md").read_text())
            self.assertIn(self.p["paths"]["module"], (out / "INSTALL.md").read_text())
            (out / "scripts/rw_init.nss").write_text("changed")
            self.assertFalse(bundles.current(self.p))
        self.assertEqual(Path(self.p["paths"]["module"]).read_bytes(), original)


@unittest.skipUnless(sys.platform == "linux", "Linux software symlinks")
class ManagedUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.p = dict(
            version=1,
            world_id="test_world",
            redis_prefix="roleweaver:test_world",
            redis_port=6379,
            dashboard_port=18748,
            paths=dict.fromkeys(profiles.PATHS, ""),
            resources=[],
            features=dict.fromkeys(profiles.FEATURES, False),
            progress={},
        )
        self.old = self.root / "releases/old"
        (self.old / "roleweaver").mkdir(parents=True)
        (self.root / "current").symlink_to(self.old)
        self.unit = self.root / "roleweaver-test_world.service"
        self.unit.write_text("original unit")
        (self.root / "config.json").write_text(
            json.dumps(
                dict(
                    world_id="test_world",
                    redis_prefix="roleweaver:test_world",
                    redis_port=6379,
                    web_port=18748,
                    model="keep-model",
                )
            )
        )
        (self.root / "provider.env").write_text("PRIVATE=preserve")
        (self.root / "data").mkdir()
        (self.root / "data/remember-me").write_text("player memory")
        self.enterContext(
            patch.object(profiles, "installation", return_value=self.root)
        )
        self.enterContext(patch.object(profiles, "save"))
        self.enterContext(patch.object(manager, "own_service"))
        self.enterContext(patch.object(manager, "active", return_value=True))
        self.enterContext(
            patch.object(
                manager, "environment", return_value=Path("/persistent/env/bin/python")
            )
        )
        self.snapshot = self.enterContext(
            patch.object(manager, "snapshot", return_value="verified-point")
        )
        self.health = self.enterContext(
            patch.object(manager, "health", return_value={})
        )
        self.commands = []
        self.enterContext(patch.object(manager, "run", side_effect=self.fake_run))

    def fake_run(self, args, **kwargs):
        args = [str(a) for a in args]
        self.commands.append(args)
        if any(a.endswith("install_companion.py") for a in args):
            target = self.root / "releases/new"
            (target / "roleweaver").mkdir(parents=True)
            manager.set_current(self.root, target)
            self.unit.write_text("new unit")

    def test_update_and_rollback_keep_memories_keys_and_config(self):
        manager.apply(self.p, update=True)
        self.assertEqual((self.root / "current").resolve().name, "new")
        archive, data = manager.rollback_candidate(self.p)
        self.assertEqual(data["recovery_point"], "verified-point")
        manager.rollback(self.p)
        self.assertEqual((self.root / "current").resolve(), self.old)
        self.assertEqual(self.unit.read_text(), "original unit")
        self.assertEqual((self.root / "data/remember-me").read_text(), "player memory")
        self.assertEqual((self.root / "provider.env").read_text(), "PRIVATE=preserve")
        self.assertEqual(
            json.loads((self.root / "config.json").read_text())["model"], "keep-model"
        )
        self.assertFalse((self.root / "setup-pending.json").exists())
        self.assertTrue(all("nwserver" not in " ".join(c) for c in self.commands))
        with self.assertRaises(ValueError):
            manager.rollback_candidate(self.p)

    def test_failed_start_restores_previous_service(self):
        self.health.side_effect = [ValueError("failed startup"), {}]
        with self.assertRaisesRegex(ValueError, "failed startup"):
            manager.apply(self.p, update=True)
        self.assertEqual((self.root / "current").resolve(), self.old)
        self.assertEqual(self.unit.read_text(), "original unit")
        self.assertFalse((self.root / "setup-pending.json").exists())

    def test_interrupted_update_recovered_and_external_release_rejected(self):
        before = manager.record(self.p)
        other = self.root / "releases/interrupted"
        (other / "roleweaver").mkdir(parents=True)
        manager.set_current(self.root, other)
        (self.root / "setup-pending.json").write_text(json.dumps(before))
        manager.recover_pending(self.p)
        self.assertEqual((self.root / "current").resolve(), self.old)
        with self.assertRaises(ValueError):
            manager.restore_service(
                self.p, dict(before, before_release="/outside/releases/unrelated")
            )

    def test_environment_failure_does_not_stop_working_service(self):
        with patch.object(
            manager, "environment", side_effect=ValueError("dependency unavailable")
        ):
            with self.assertRaises(ValueError):
                manager.apply(self.p, update=True)
        self.assertEqual(self.commands, [])
        self.assertEqual((self.root / "current").resolve(), self.old)


if __name__ == "__main__":
    unittest.main()
