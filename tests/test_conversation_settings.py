import json
from pathlib import Path
import tempfile
import time
import unittest
from roleweaver import conversation, backup
from roleweaver.service import Service


class FakeRedis:
    def __init__(self):
        self.commands = []

    def call(self, *args):
        self.commands.append(args)
        return 1


class ConversationSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Service(
            Path(self.temp.name), dict(provider="offline", world_id="test")
        )
        self.app.redis = FakeRedis()

    def tearDown(self):
        self.app.pool.shutdown()
        self.app.store.db.close()
        self.temp.cleanup()

    def hello(self, **values):
        return dict(
            kind="hello",
            world="test",
            session="game",
            tick=100,
            conversation_protocol=2,
            conversation=conversation.wire(conversation.DEFAULTS),
            conversation_revision="",
            **values,
        )

    def test_validation(self):
        for key, value in [
            ("selection_range", 0),
            ("selection_range", 7),
            ("follow_hearing", 1),
            ("close_range", 0),
            ("hearing_range", 21),
            ("timeout", 14),
            ("timeout", 301),
            ("close_range", True),
            ("timeout", 60.5),
            ("direct_address", 1),
            ("line_of_sight", "false"),
        ]:
            with self.assertRaises(ValueError):
                conversation.settings(dict(conversation.DEFAULTS, **{key: value}))
        with self.assertRaises(ValueError):
            conversation.settings(dict(conversation.DEFAULTS, close_range=11))
        with self.assertRaises(ValueError):
            conversation.settings({})
        self.assertEqual(conversation.settings(), conversation.DEFAULTS)

    def test_sync_requires_fresh_matching_game_confirmation_and_throttles(self):
        self.assertEqual(self.app.conversation_status()["status"], "offline")
        hello = self.hello()
        self.app.sync_conversation(hello)
        self.assertEqual(self.app.conversation_status()["status"], "pending")
        command = json.loads(self.app.redis.commands[-1][-1])
        self.assertEqual(command["expires"], 105)
        self.assertEqual(command["world"], "test")
        self.assertEqual(command["revision"], self.app.conversation_revision)
        self.app.sync_conversation(hello)
        self.assertEqual(len(self.app.redis.commands), 1)
        hello["conversation_revision"] = self.app.conversation_revision
        self.app.sync_conversation(hello)
        self.assertEqual(self.app.conversation_status()["status"], "applied")
        self.app.conversation_hello["seen"] = time.monotonic() - 10
        self.assertEqual(self.app.conversation_status()["status"], "offline")

    def test_wrong_world_old_bridge_and_stale_values_never_confirm(self):
        hello = self.hello()
        hello["world"] = "other"
        self.app.sync_conversation(hello)
        self.assertFalse(self.app.redis.commands)
        hello = self.hello()
        hello.pop("conversation_protocol")
        self.app.sync_conversation(hello)
        self.assertEqual(self.app.conversation_status()["status"], "upgrade_required")
        self.assertFalse(self.app.redis.commands)
        hello = self.hello()
        hello["conversation_revision"] = self.app.conversation_revision
        hello["conversation"]["timeout"] = 90
        self.app.sync_conversation(hello)
        self.assertEqual(self.app.conversation_status()["status"], "pending")

    def test_save_and_reset_persist_and_invalidate_inflight_generations(self):
        self.app.busy.add("mira")
        old = self.app.conversation_revision
        p = dict(
            conversation.DEFAULTS, close_range=5, timeout=120, direct_address=False
        )
        self.app.save_conversation(p)
        self.assertNotEqual(old, self.app.conversation_revision)
        self.assertEqual(self.app.generations["mira"], 1)
        self.assertEqual(self.app.setting("conversation", None), p)
        revision = self.app.conversation_revision
        self.app.save_conversation(p)
        self.assertEqual(revision, self.app.conversation_revision)
        self.app.save_conversation(p, reset=True)
        self.assertNotEqual(revision, self.app.conversation_revision)
        self.assertEqual(self.app.generations["mira"], 2)

    def test_reconnect_and_new_session_resend(self):
        hello = self.hello()
        self.app.sync_conversation(hello)
        hello["session"] = "restarted"
        hello["tick"] = 1
        self.app.sync_conversation(hello)
        self.assertEqual(len(self.app.redis.commands), 2)
        self.assertEqual(
            json.loads(self.app.redis.commands[-1][-1])["session"], "restarted"
        )

    def test_backup_roundtrip_and_legacy_preservation(self):
        p = dict(conversation.DEFAULTS, timeout=90)
        self.app.save_conversation(p)
        data = backup.export(self.app.store, self.app.salt)
        self.assertEqual(data["version"], 11)
        checked = backup.validate(data)
        self.assertEqual(checked["conversation"], p)
        self.app.save_conversation(conversation.DEFAULTS)
        backup.replace(self.app.store, checked)
        self.assertEqual(self.app.setting("conversation", None), p)
        data["version"] = 5
        data.pop("conversation")
        legacy = backup.validate(data)
        backup.replace(self.app.store, legacy)
        self.assertEqual(self.app.setting("conversation", None), p)
        data["version"] = 6
        with self.assertRaises(ValueError):
            backup.validate(data)

    def test_legacy_settings_and_backup_keep_custom_values(self):
        old = dict(
            close_range=4,
            hearing_range=12,
            timeout=90,
            line_of_sight=False,
            direct_address=False,
        )
        new = conversation.migrate(old)
        self.assertEqual(new, dict(old, selection_range=4, follow_hearing=False))
        self.app.set_setting("conversation", old)
        data = self.app.backup_data()
        self.assertEqual(data["conversation"], new)
        data["version"] = 7
        data["conversation"] = old
        self.assertEqual(backup.validate(data)["conversation"], new)
        data["version"] = 8
        with self.assertRaises(ValueError):
            backup.validate(data)
        with self.assertRaises(ValueError):
            self.app.save_conversation(old)

    def test_old_game_protocol_requires_upgrade(self):
        hello = self.hello()
        hello["conversation_protocol"] = 1
        self.app.sync_conversation(hello)
        self.assertEqual(self.app.conversation_status()["status"], "upgrade_required")
        self.assertFalse(self.app.redis.commands)

    def test_new_defaults_and_settings_roundtrip(self):
        self.assertEqual(self.app.conversation_policy["selection_range"], 3)
        self.assertEqual(self.app.conversation_policy["close_range"], 6)
        self.assertEqual(self.app.conversation_policy["timeout"], 180)
        self.assertTrue(self.app.conversation_policy["follow_hearing"])
        p = dict(
            conversation.DEFAULTS,
            selection_range=2,
            close_range=5,
            follow_hearing=False,
        )
        self.app.save_conversation(p)
        self.assertEqual(backup.validate(self.app.backup_data())["conversation"], p)

    def test_stale_conversation_chat_is_not_stored(self):
        self.app.event(
            dict(
                kind="state",
                npc="mira",
                session="game",
                epoch=1,
                tick=100,
                mode="auto",
                object="npc",
            )
        )
        self.app.event(
            dict(
                kind="chat",
                npc="mira",
                session="game",
                epoch=1,
                event_id="old",
                player="key:name",
                text="stale",
                conversation_revision="old",
            )
        )
        self.assertFalse(self.app.store.transcript("mira"))


if __name__ == "__main__":
    unittest.main()
