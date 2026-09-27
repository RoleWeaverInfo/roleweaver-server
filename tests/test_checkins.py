import time
import unittest
from unittest.mock import patch
from tests import test_actions
from roleweaver import patrol, actions
from roleweaver.store import DEFAULT_NPC


class CheckinTests(unittest.TestCase):
    setUp = test_actions.ActionsTests.setUp
    tearDown = test_actions.ActionsTests.tearDown

    def test_generation_reviews_and_waits_for_game_before_recording(self):
        item = self.ready()
        self.app.checkin_working = 1
        with (
            patch(
                "roleweaver.checkins.provider.reply",
                return_value="Everything quiet today?",
            ) as reply,
            patch.object(self.app, "review_dialogue", return_value="allow"),
            patch.object(self.app.validation, "check", return_value=""),
        ):
            self.app.generate_checkin(item)
        command = self.app.redis.last()
        self.assertEqual(command["kind"], "checkin_say")
        self.assertEqual(command["peer"], "mira")
        self.assertEqual(self.app.store.transcript("guard"), [])
        self.assertNotIn("controlled_actions", reply.call_args.args[1])
        self.assertEqual(self.app.checkin_working, 0)

    def test_late_generation_is_discarded_after_player_interrupt(self):
        item = self.ready()
        self.app.checkin_working = 1

        def response(*args):
            self.app.cancel_checkin("guard", "Player speaking")
            return "A late reply"

        with (
            patch("roleweaver.checkins.provider.reply", side_effect=response),
            patch.object(self.app, "review_dialogue", return_value="allow"),
            patch.object(self.app.validation, "check", return_value=""),
        ):
            self.app.generate_checkin(item)
        self.assertEqual(self.app.redis.commands, [])
        self.assertEqual(self.app.store.transcript("guard"), [])

    def test_failed_safeguard_review_never_speaks(self):
        item = self.ready()
        self.app.checkin_working = 1
        with (
            patch.object(self.app, "review_dialogue", return_value="block"),
            patch.object(self.app.validation, "check", return_value=""),
            patch("roleweaver.checkins.provider.reply") as reply,
        ):
            self.app.generate_checkin(item)
            reply.assert_not_called()
        self.assertIsNone(self.app.checkin)
        self.assertEqual(self.app.redis.commands, [])

    def ready(self):
        app = self.app
        app.store.save(dict(DEFAULT_NPC, id="guard", name="Guard", mode="auto"))
        app.states["guard"] = dict(
            self.state, nearby_npcs=["mira"], checkins_protocol=1, conversation_active=0
        )
        app.states["mira"].update(
            nearby_npcs=["guard"], checkins_protocol=1, conversation_active=0
        )
        self.duty = dict(patrol.DEFAULT, checkins={"inn": "mira"}, checkin_cooldown=300)
        with patch.object(app.pool, "submit") as submit:
            app.start_checkin("guard", "inn", self.duty)
            self.assertEqual(submit.call_count, 1)
        app.checkin_working = 0
        return app.checkin

    def test_two_confirmed_turns_are_attributed_and_duplicates_ignored(self):
        item = self.ready()
        item["request"] = "first"
        pending = dict(
            npc="guard", peer="mira", text="All well?", checkin_id=item["id"]
        )
        event = dict(request="first", world="test", session="game", epoch=1, ok=1)
        with patch.object(self.app.pool, "submit") as submit:
            self.app.checkin_ack(pending, event)
            self.assertEqual(submit.call_count, 1)
        self.assertEqual(item["turn"], 1)
        self.assertIn(
            "reported (unverified)",
            self.app.store.transcript("mira", "npc:guard")[-1]["text"],
        )
        item["request"] = "second"
        self.app.checkin_ack(
            dict(npc="mira", peer="guard", text="Quiet here.", checkin_id=item["id"]),
            dict(event, request="second"),
        )
        self.assertIsNone(self.app.checkin)
        before = len(self.app.store.transcript("mira"))
        self.app.checkin_ack(pending, event)
        self.assertEqual(before, len(self.app.store.transcript("mira")))

    def test_interruption_and_timeout(self):
        item = self.ready()
        self.app.states["mira"]["conversation_active"] = 1
        self.app.checkin_tick()
        self.assertIsNone(self.app.checkin)
        self.app.states["mira"]["conversation_active"] = 0
        self.app.checkin_last.clear()
        item = self.ready()
        item["deadline"] = time.monotonic() - 1
        self.app.checkin_tick()
        self.assertIsNone(self.app.checkin)

    def test_cooldown_survives_settings_reload_and_old_bridge_cannot_start(self):
        self.ready()
        self.app.cancel_checkin("guard")
        self.app.checkin_last = self.app.setting("checkin_last", {})
        with patch.object(self.app.pool, "submit") as submit:
            self.app.start_checkin("guard", "inn", self.duty)
            submit.assert_not_called()
            self.app.checkin_last.clear()
            self.app.states["mira"]["checkins_protocol"] = 0
            self.app.start_checkin("guard", "inn", self.duty)
            submit.assert_not_called()

    def test_configuration_migrates_and_rejects_unapproved_stops(self):
        old = dict(patrol.DEFAULT, route=["inn", "inn"])
        self.assertEqual(patrol.validate(old, ["inn"])["checkins"], {})
        with self.assertRaises(ValueError):
            patrol.validate(dict(old, checkins={"unknown": "mira"}), ["inn"])
        with self.assertRaises(ValueError):
            patrol.validate(dict(old, checkin_cooldown=0), ["inn"])

    def test_rejected_or_wrong_session_speech_is_not_remembered(self):
        item = self.ready()
        item["request"] = "one"
        pending = dict(npc="guard", peer="mira", text="hello", checkin_id=item["id"])
        self.app.checkin_ack(
            pending, dict(request="one", world="test", session="old", epoch=1, ok=1)
        )
        self.assertEqual(self.app.store.transcript("mira"), [])
        self.app.checkin_ack(
            pending, dict(request="one", world="test", session="game", epoch=1, ok=0)
        )
        self.assertEqual(self.app.store.transcript("mira"), [])
        self.assertIsNone(self.app.checkin)
