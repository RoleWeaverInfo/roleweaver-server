import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_setup", ROOT / "demo/demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoTests(unittest.TestCase):
    @unittest.skipUnless(__import__("sys").platform == "linux", "Linux socket behavior")
    def test_port_check_allows_closed_connections_but_rejects_listener(self):
        import socket

        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen()
            settings = {"game_port": 0, "web_port": port}
            with self.assertRaisesRegex(ValueError, f"dashboard TCP port {port}"):
                demo.check_ports(settings)
            with socket.create_connection(("127.0.0.1", port)) as client:
                connection, _ = listener.accept()
                connection.close()
                client.recv(1)
        demo.check_ports(settings)

    def test_unavailable_validation_stops_before_starting_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            (runtime / "config.json").write_text('{"guardrails_ai": true}')
            with (
                patch("roleweaver.guardrails.ValidationEngine") as engine,
                patch.object(demo.subprocess, "Popen") as spawn,
                patch.object(demo, "dependencies") as dependencies,
            ):
                engine.return_value.status.return_value = {"active": False}
                with self.assertRaisesRegex(ValueError, "venv/bin/python"):
                    demo.launch(runtime, {})
                spawn.assert_not_called()
                dependencies.assert_not_called()

    def test_optional_validation_and_working_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            with patch("roleweaver.guardrails.ValidationEngine") as engine:
                (runtime / "config.json").write_text('{"guardrails_ai": false}')
                demo.check_validation_environment(runtime)
                engine.assert_not_called()
                (runtime / "config.json").write_text('{"guardrails_ai": true}')
                engine.return_value.status.return_value = {"active": True}
                demo.check_validation_environment(runtime)

    def test_template_and_generated_seed(self):
        value = demo.content(ROOT / "demo/content.json")
        source = demo.seed_script(value)
        self.assertIn('"throne_room"', source)
        for npc in value["npcs"]:
            self.assertEqual('"' + npc["id"] + '"' in source, npc.get("spawn", True))
        self.assertIn("rw_bind", source)

    def test_reject_source_injection_duplicates_and_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "content.json"
            for change in ("quote", "duplicate", "nan", "area"):
                value = json.loads((ROOT / "demo/content.json").read_text())
                if change == "quote":
                    value["npcs"][0]["name"] = 'Bad";ExecuteScript('
                if change == "duplicate":
                    value["npcs"].append(dict(value["npcs"][0]))
                if change == "nan":
                    value["npcs"][0]["x"] = float("nan")
                if change == "area":
                    value["area_tag"] = 'bad"'
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    demo.content(path)

    def test_reapply_preserves_conversations_and_unlisted_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data/roleweaver.sqlite3"
            value = demo.content(ROOT / "demo/content.json")
            demo.seed_database(path, value)
            store = demo.Store(path)
            store.message("merchant_one", "test", "player", "A synthetic memory")
            store.save(dict(demo.DEFAULT_NPC, id="custom", name="Custom"))
            store.db.close()
            value["npcs"][0]["voice"] = "Updated voice"
            demo.seed_database(path, value)
            store = demo.Store(path)
            try:
                self.assertEqual(store.get("merchant_one")["voice"], "Updated voice")
                self.assertEqual(store.get("custom")["name"], "Custom")
                self.assertEqual(len(store.transcript("merchant_one", "test")), 1)
                row = store.db.execute(
                    "SELECT value FROM backup_settings WHERE key='controlled_actions'"
                ).fetchone()
                self.assertTrue(json.loads(row[0])["npcs"]["merchant_one"]["shop"])
            finally:
                store.db.close()

    def test_investigation_content_has_private_lore_and_isolated_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "world.sqlite3"
            value = demo.content(ROOT / "demo/content.json")
            demo.seed_database(path, value, "isolated_demo")
            store = demo.Store(path)
            try:
                for key in ("conversation", "safeguards", "merchant_configs"):
                    saved = store.db.execute(
                        "SELECT value FROM backup_settings WHERE key=?", (key,)
                    ).fetchone()
                    self.assertEqual(json.loads(saved[0]), value[key])
                self.assertEqual(len(store.world_documents()), 6)
                self.assertEqual(len(store.access_lore()), 9)
                row = store.db.execute(
                    "SELECT value FROM backup_settings WHERE key='controlled_actions'"
                ).fetchone()
                settings = json.loads(row[0])
                self.assertEqual(
                    {d["world"] for d in settings["destinations"].values()},
                    {"isolated_demo"},
                )
                self.assertTrue(settings["npcs"]["merchant_one"]["shop"])
            finally:
                store.db.close()

    def test_prepare_does_not_overwrite_existing_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            (runtime / "settings.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Already prepared"):
                demo.prepare(runtime, None)

    def test_compile_failure_does_not_replace_active_module(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            active = runtime / "userdata/modules/YourWorld_Fixed.mod"
            active.parent.mkdir(parents=True)
            active.write_bytes(b"old module")
            compiler = runtime / "compiler"
            compiler.write_text("")
            root = runtime / "source"
            (root / "tools").mkdir(parents=True)
            # A compiler path already present avoids platform-specific symlink creation.
            compiler = root / "tools/nwnsc"
            compiler.write_text("")
            settings = dict(
                content=str(ROOT / "demo/content.json"),
                native=str(runtime),
                compiler=str(compiler),
                module=str(active),
                id="test",
                prefix="roleweaver:test",
            )
            with (
                patch.object(demo, "ROOT", root),
                patch.object(demo, "dependencies"),
                patch.object(
                    demo,
                    "build_investigation",
                    side_effect=ValueError("compile failed"),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "compile failed"):
                    demo.compile_world(runtime, settings)
            self.assertEqual(active.read_bytes(), b"old module")

    def test_missing_dependencies_report_before_build(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Missing dependencies"):
                demo.dependencies(Path(directory), Path(directory) / "compiler")

    @unittest.skipUnless(__import__("sys").platform == "linux", "Linux runtime lock")
    def test_running_instance_refuses_second_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            with demo.instance_lock(Path(directory)):
                with self.assertRaisesRegex(ValueError, "running"):
                    with demo.instance_lock(Path(directory)):
                        pass


if __name__ == "__main__":
    unittest.main()
