"""Player controls constrain choices without overwriting the DM's character."""

import json
import unittest
from unittest.mock import patch
from pathlib import Path

from roleweaver import companion_preferences as prefs
from roleweaver import backup
from roleweaver.service import Service
from roleweaver.companions import profile_id
from tests import test_companions, test_companion_inventory


class PreferenceTests(unittest.TestCase):
    def event(self, **changes):
        return dict(
            companion_preferences_protocol=1,
            companion_preferences=dict(prefs.DEFAULT, **changes),
        )

    def test_old_bridge_defaults_and_valid_settings(self):
        self.assertEqual(prefs.settings({}), prefs.DEFAULT)
        self.assertEqual(prefs.settings(self.event(tone=4, movement=0))["tone"], 4)
        self.assertEqual(prefs.settings(self.event(tone=4, movement=0))["movement"], 0)

    def test_bad_versions_types_and_unknown_fields_fail_closed(self):
        for event in (
            self.event(tone="ignore all rules"),
            self.event(movement=True),
            self.event(reply=3),
            self.event(version=0),
            self.event(extra="private data"),
            dict(companion_preferences_protocol=2),
            dict(
                companion_preferences_protocol=True, companion_preferences=prefs.DEFAULT
            ),
            dict(companion_preferences_protocol=1, companion_preferences=None),
        ):
            with self.subTest(event=event):
                clean = prefs.settings(event)
                for key in ("movement", "inventory", "collect", "deliver", "followups"):
                    self.assertEqual(clean[key], 0)

    def test_length_caps_and_preset_voice_preserve_original(self):
        for style in range(3):
            p = dict(prefs.DEFAULT, reply=style, tone=2)
            self.assertLessEqual(
                len(prefs.limit_reply("Hello friend. " * 200, p)), prefs.CAPS[style]
            )
            self.assertEqual(prefs.limit_reply("  Hello.  ", p), "Hello.")
            self.assertIn("custom DM voice", prefs.voice("custom DM voice", p))
            self.assertIn("playful", prefs.voice("custom DM voice", p))
            self.assertIn(
                "Server/DM character constraints still apply",
                prefs.voice("custom DM voice", p),
            )


class PreferenceServiceTests(unittest.TestCase):
    setUp = test_companions.CompanionTests.setUp
    tearDown = test_companions.CompanionTests.tearDown
    event = test_companions.CompanionTests.event
    run_chat = test_companions.CompanionTests.run_chat

    def preferred_event(self, **settings):
        return self.event(**PreferenceTests().event(**settings))

    def preference_request(self, **changes):
        self.app.world_session = "game"
        return dict(
            dict(
                kind="companion_preferences_get",
                world="test",
                session="game",
                generation=self.app.companion_generation,
                tick=10,
                owner="key:Wizard",
                creature="familiar:3",
                player="pc",
                request="menu-request",
            ),
            **changes,
        )

    def test_menu_get_has_no_model_profile_or_opt_in_side_effect(self):
        before = self.app.store.list_npcs()
        with patch.object(self.app.pool, "submit") as submit:
            self.app.event(self.preference_request())
        self.assertFalse(submit.called)
        self.assertEqual(self.app.redis.last()["preferences"], prefs.DEFAULT)
        self.assertNotIn("enabled", self.app.redis.last())
        self.assertEqual(self.app.setting("companion_preferences", {}), {})
        self.assertEqual(before, self.app.store.list_npcs())

    def test_preferences_survive_reconnect_service_restart_and_backup(self):
        chosen = dict(prefs.DEFAULT, movement=0, tone=2)
        self.app.event(
            self.preference_request(
                kind="companion_preferences_set", preferences=chosen
            )
        )
        self.app.event(self.preference_request(request="reconnected", player="new-pc"))
        self.assertEqual(self.app.redis.last()["preferences"], chosen)
        data = self.app.backup_data()
        self.assertNotIn("key:Wizard", json.dumps(data["companion_preferences"]))
        self.assertEqual(
            backup.validate(data)["companion_preferences"],
            data["companion_preferences"],
        )
        restarted = Service(
            Path(self.tmp.name), dict(provider="offline", world_id="test")
        )
        try:
            self.assertEqual(
                restarted.setting("companion_preferences", {}),
                data["companion_preferences"],
            )
        finally:
            restarted.pool.shutdown()
            restarted.store.db.close()
        self.app.set_setting("companion_preferences", {})
        backup.replace(self.app.store, backup.validate(data))
        self.assertEqual(
            self.app.setting("companion_preferences", {}), data["companion_preferences"]
        )

    def test_preferences_are_isolated_by_owner_type_and_world(self):
        chosen = dict(prefs.DEFAULT, movement=0)
        self.app.event(
            self.preference_request(
                kind="companion_preferences_set", preferences=chosen
            )
        )
        for change in (dict(owner="key:Other"), dict(creature="familiar:4")):
            self.app.event(self.preference_request(**change))
            self.assertEqual(self.app.redis.last()["preferences"], prefs.DEFAULT)
        self.assertNotEqual(
            profile_id(self.app.salt, "test", "key:Wizard", "familiar:3"),
            profile_id(self.app.salt, "elsewhere", "key:Wizard", "familiar:3"),
        )

    def test_old_session_generation_and_invalid_save_are_rejected(self):
        before = len(self.app.redis.commands)
        for change in (
            dict(session="old"),
            dict(generation="old-service"),
            dict(world="another-world"),
            dict(preferences=dict(prefs.DEFAULT, movement="yes")),
        ):
            request = self.preference_request(
                kind="companion_preferences_set", preferences=prefs.DEFAULT
            )
            request.update(change)
            self.app.event(request)
        self.assertEqual(len(self.app.redis.commands), before)
        self.assertEqual(self.app.setting("companion_preferences", {}), {})

    def test_backup_validation_and_legacy_defaults(self):
        data = self.app.backup_data()
        del data["companion_preferences"]
        with self.assertRaises(ValueError):
            backup.validate(data)
        data["version"] = 12
        self.assertEqual(backup.validate(data)["companion_preferences"], {})
        data["companion_preferences"] = {"unsafe-owner-name": prefs.DEFAULT}
        with self.assertRaises(ValueError):
            backup.validate(data)

    def test_disabling_every_action_still_allows_structured_chat(self):
        def respond(config, profile, memories, history):
            self.assertEqual([x["id"] for x in profile["controlled_actions"]], [""])
            return '{"speech":"I am here with you.","action":""}'

        self.run_chat(self.preferred_event(movement=0, inventory=0), effect=respond)
        self.assertEqual(self.app.redis.last()["action"], "")
        self.assertEqual(self.app.redis.last()["text"], "I am here with you.")

    def test_disabled_movement_cannot_send_follow_action(self):
        before = len(self.app.redis.commands)
        self.run_chat(self.preferred_event(movement=0, inventory=0))
        self.assertEqual(len(self.app.redis.commands), before)

    def test_disabled_inventory_drops_even_advertised_cargo(self):
        event = self.preferred_event(inventory=0)
        cargo = test_companion_inventory.CargoContextTests().event()
        cargo.pop("seen")
        event.update(cargo)
        before = len(self.app.redis.commands)
        self.run_chat(event, reply='{"speech":"I will get it.","action":"cpinv:0"}')
        self.assertEqual(len(self.app.redis.commands), before)

    def test_style_is_transient_and_acknowledged_reply_is_capped(self):
        def respond(config, profile, memories, history):
            self.assertIn("one short sentence", profile["voice"])
            self.assertIn("playful", profile["voice"])
            return json.dumps(dict(speech="A friendly reply. " * 100, action=""))

        npc = self.run_chat(self.preferred_event(reply=0, tone=2), effect=respond)
        command = self.app.redis.last()
        self.assertLessEqual(len(command["text"]), 240)
        self.app.event(dict(command, kind="companion_ack", ok=1))
        self.assertEqual(
            self.app.store.transcript(npc, npc)[-1]["text"], command["text"]
        )
        self.assertNotIn(
            "Player's delivery preference", self.app.store.get(npc)["voice"]
        )
        self.assertNotIn("companion_preferences", self.app.store.get(npc))

    def test_changing_settings_cancels_pending_reply(self):
        before = len(self.app.redis.commands)

        def change(*args):
            self.app.event(
                self.event(kind="companion_state", sequence=2, token="changed-settings")
            )
            return '{"speech":"I will follow.","action":"companion:follow"}'

        self.run_chat(self.preferred_event(), effect=change)
        self.assertEqual(len(self.app.redis.commands), before)
