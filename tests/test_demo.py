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
    def test_seeded_demo_starts_recovery_runtime_and_keeps_player_identity(self):
        from roleweaver.recovery_runtime import RecoveryRuntime

        value = demo.content(ROOT / "demo/content.json")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "roleweaver.sqlite3"
            demo.seed_database(path, value, "clean_demo")
            salt = (root / "identity_salt").read_text()
            runtime = RecoveryRuntime(
                root,
                {"provider": "offline", "world_id": "clean_demo"},
                start_workers=False,
            )
            try:
                self.assertEqual(runtime.error, "")
                self.assertIsNotNone(runtime.app)
                self.assertEqual(runtime.app.salt, salt)
            finally:
                runtime.close()
            demo.seed_database(path, value, "clean_demo")
            self.assertEqual((root / "identity_salt").read_text(), salt)

    def test_reimport_does_not_replace_a_missing_existing_player_identity(self):
        from roleweaver.recovery_runtime import RecoveryRuntime

        value = demo.content(ROOT / "demo/content.json")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "roleweaver.sqlite3"
            demo.seed_database(path, value, "clean_demo")
            (root / "identity_salt").unlink()
            demo.seed_database(path, value, "clean_demo")
            self.assertFalse((root / "identity_salt").exists())
            runtime = RecoveryRuntime(
                root, {"provider": "offline"}, start_workers=False
            )
            try:
                self.assertIn("Player identity file is missing", runtime.error)
                self.assertIsNone(runtime.app)
            finally:
                runtime.close()

    def test_fresh_demo_has_authored_content_without_player_or_translation_history(
        self,
    ):
        from roleweaver.translation import TranslationCache

        value = demo.content(ROOT / "demo/content.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "world.sqlite3"
            demo.seed_database(path, value, "clean_demo")
            store = demo.Store(path)
            translations = TranslationCache(Path(directory) / "translations.sqlite3")
            try:
                self.assertEqual(
                    {npc["id"] for npc in store.list_npcs()},
                    {npc["id"] for npc in value["npcs"]},
                )
                for table in (
                    "memories",
                    "messages",
                    "story_visits",
                    "seen",
                    "placements",
                    "safeguard_events",
                ):
                    with self.subTest(table=table):
                        self.assertEqual(
                            store.db.execute(
                                f"SELECT COUNT(*) FROM {table}"
                            ).fetchone()[0],
                            0,
                        )
                for table, source in (
                    ("world_documents", "world_documents"),
                    ("access_lore", "access_lore"),
                ):
                    self.assertEqual(
                        store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                        len(value[source]),
                    )
                for table in ("entries", "current_sources", "preferences"):
                    self.assertEqual(
                        translations.db.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0],
                        0,
                    )
            finally:
                store.db.close()
                translations.db.close()

    def test_encounters_spawn_in_their_areas_and_seed_without_resetting_a_run(self):
        value = demo.content(ROOT / "demo/content.json")
        script = demo.seed_script(value)
        self.assertIn('area=GetObjectByTag("rw_cave")', script)
        self.assertIn('area=GetObjectByTag("rw_forest")', script)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "world.sqlite3"
            demo.seed_database(path, value, "test_world")
            store = demo.Store(path)
            self.assertEqual(
                {n["id"] for n in store.list_npcs()}, {n["id"] for n in value["npcs"]}
            )
            data = json.loads(
                store.db.execute(
                    "SELECT value FROM backup_settings WHERE key='encounters'"
                ).fetchone()[0]
            )
            self.assertEqual(set(data["runs"]), {"forest_robbery", "troll_ransom"})
            self.assertTrue(
                all(
                    r["status"] == "waiting" and r["world"] == "test_world"
                    for r in data["runs"].values()
                )
            )
            captive = next(
                a
                for a in data["templates"]["troll_ransom"]["actors"]
                if a["npc"] == "elana_voss"
            )
            self.assertFalse(captive["combatant"])
            data["runs"]["troll_ransom"]["stage"] = "negotiation"
            with store.db:
                store.db.execute(
                    "UPDATE backup_settings SET value=? WHERE key='encounters'",
                    (json.dumps(data),),
                )
            store.db.close()
            demo.seed_database(path, value, "test_world")
            store = demo.Store(path)
            again = json.loads(
                store.db.execute(
                    "SELECT value FROM backup_settings WHERE key='encounters'"
                ).fetchone()[0]
            )
            self.assertEqual(again["runs"], data["runs"])
            store.db.close()

    def test_rebuild_refreshes_bridge_without_changing_authored_resources(self):
        import sys

        sys.path.insert(0, str(ROOT / "demo/investigation"))
        from runtime import refresh_bridge
        from module_copy import resources
        from prepare_addon import ENTRIES, INCLUDES

        entries = {
            (n, k): raw
            for n, k, raw in resources(
                (ROOT / "demo/world/YourWorld_Fixed.mod").read_bytes()
            )
        }
        # Model an old editable module and preserve all of its authored layout.
        entries["rw_tick", 2009] = b"old bridge"
        entries.pop(("rw_health", 2009), None)
        before = dict(entries)
        refresh_bridge(entries)
        for name in (*ENTRIES, *INCLUDES):
            self.assertEqual(
                entries[name, 2009], (ROOT / "bridge" / (name + ".nss")).read_bytes()
            )
        for key in before:
            if key[1] in (2014, 2023, 2012, 2046) or key[0].startswith("rq_"):
                self.assertEqual(entries[key], before[key])
        self.assertIn(("rw_tr_demo", 2029), entries)

    def test_dm_password_reset_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            settings = {
                "dm_password": "previous-password",
                "id": "custom_demo",
                "game_port": 5127,
                "native": "/existing/runtime",
            }
            demo.reset_dm_password(runtime, settings)
            saved = json.loads((runtime / "settings.json").read_text())
            self.assertEqual(saved, dict(settings, dm_password="roleweaver"))
            self.assertEqual(settings["dm_password"], "previous-password")

    def test_connection_output_uses_configured_ports_and_tunnel(self):
        text = demo.connection_instructions(
            {"game_port": 5133, "web_port": 8759}, ["192.168.167.128"], "roleweaver"
        )
        self.assertIn("192.168.167.128:5133", text)
        self.assertIn("127.0.0.1:5133", text)
        self.assertIn("http://127.0.0.1:8759", text)
        self.assertIn("ssh -N -L 8759:127.0.0.1:8759 roleweaver@192.168.167.128", text)
        self.assertNotIn("http://192.168.167.128", text)

    def test_connection_output_missing_or_multiple_addresses(self):
        settings = {"game_port": 5125, "web_port": 8745}
        self.assertIn("hostname -I", demo.connection_instructions(settings, [], "user"))
        text = demo.connection_instructions(
            settings, ["10.0.0.2", "192.168.1.2"], "user"
        )
        self.assertIn("10.0.0.2:5125", text)
        self.assertIn("192.168.1.2:5125", text)
        self.assertIn("user@UBUNTU-IP", text)

    def test_address_detection_filters_and_handles_missing_ip_command(self):
        data = [
            {
                "addr_info": [
                    {"scope": "host", "local": "127.0.0.1"},
                    {"scope": "global", "local": "192.168.1.2"},
                ]
            }
        ]
        with patch.object(demo.subprocess, "run") as run:
            run.return_value.stdout = json.dumps(data)
            self.assertEqual(demo.host_ipv4_addresses(), ["192.168.1.2"])
            run.side_effect = FileNotFoundError()
            self.assertEqual(demo.host_ipv4_addresses(), [])

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
