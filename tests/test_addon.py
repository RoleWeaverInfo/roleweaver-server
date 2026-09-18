import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import build_addon


class AddonTests(unittest.TestCase):
    def test_default_settings_preserve_world_and_chat_ownership(self):
        value = build_addon.settings("test_world", "roleweaver:test_world")
        self.assertIn("RW_OWNS_PLACEMENTS = 0", value)
        self.assertIn("RW_REGISTERS_CHAT = 0", value)

    def test_world_id_cannot_inject_nwscript(self):
        with self.assertRaises(ValueError):
            build_addon.settings('world";\n', "test")

    def test_audit_detects_compiled_chat_registration_and_collision(self):
        entries = [
            ("module", 2014, b"gff"),
            ("world_chat", 2010, b"binary RegisterChatScript content"),
            ("rw_init", 2009, b"void main() {}"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "world.mod"
            module.write_bytes(b"module")
            with (
                patch.object(build_addon, "resources", return_value=entries),
                patch.object(
                    build_addon,
                    "simple_fields",
                    return_value={"Mod_OnModLoad": "world_load"},
                ),
            ):
                report = build_addon.audit(module)
        self.assertEqual(report["possible_chat_registrations"], ["world_chat.ncs"])
        self.assertEqual(report["reserved_resource_collisions"], ["rw_init"])

    def test_exclusive_mode_refuses_known_existing_chat_owner_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "bundle"
            with patch.object(
                build_addon,
                "audit",
                return_value={
                    "reserved_resource_collisions": [],
                    "possible_chat_registrations": ["world_chat.ncs"],
                },
            ):
                with self.assertRaisesRegex(ValueError, "Existing chat registration"):
                    build_addon.build(
                        Path("world.mod"),
                        out,
                        Path("native"),
                        "world",
                        "rw:world",
                        "world",
                        "exclusive",
                    )
            self.assertFalse(out.exists())

    def test_audit_includes_supplied_override_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "world.mod"
            module.write_bytes(b"module")
            scripts = root / "override"
            scripts.mkdir()
            collision = scripts / "rw_tick.ncs"
            collision.write_bytes(b"existing custom script")
            with (
                patch.object(
                    build_addon, "resources", return_value=[("module", 2014, b"gff")]
                ),
                patch.object(build_addon, "simple_fields", return_value={}),
            ):
                report = build_addon.audit(module, [scripts])
            self.assertIn(
                str(collision.resolve()), report["reserved_resource_collisions"]
            )
