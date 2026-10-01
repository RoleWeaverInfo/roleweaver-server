"""Autonomous cast speech stays scoped, bounded and subordinate to player input."""

import time
import unittest
from unittest.mock import patch
from tests import test_director
from roleweaver import guardrails


class SceneDialogueTests(unittest.TestCase):
    setUp = test_director.DirectorTests.setUp
    tearDown = test_director.DirectorTests.tearDown
    place = test_director.DirectorTests.place
    confirm = test_director.DirectorTests.confirm
    prepare = test_director.DirectorTests.prepare
    review = test_director.DirectorTests.review
    result = test_director.DirectorTests.result

    def ready(self):
        key, scene = self.prepare()
        scene["director"]["summary"] = "The visitors are negotiating."
        self.app.director_presence[key] = dict(
            players=["visitor-test"], seen=time.monotonic()
        )
        for n in scene["actors"]:
            self.app.states[n].update(
                seen=time.monotonic(),
                checkins_protocol=1,
                scene_speech_protocol=1,
                scene_speech_status="engaged",
                area="hall",
                x=1,
                y=1,
                conversation_active=True,
            )
            self.app.action_config["npcs"].setdefault(n, {})["nearby"] = dict(
                talk=True, receive=True, radius=12
            )
        return key, scene

    def test_director_owns_resolution_but_warning_and_attack_remain_available(self):
        key, scene = self.ready()
        npc = next(iter(scene["actors"]))
        choices, _ = self.app.live_combat_choices(
            npc, dict(event_id="turn", attack_ready=False)
        )
        self.assertEqual([c["id"] for c in choices], ["encounter:warn"])
        choices, _ = self.app.live_combat_choices(
            npc, dict(event_id="turn", attack_ready=True)
        )
        self.assertEqual([c["id"] for c in choices], ["encounter:attack"])

    def test_first_reply_can_clear_no_player_hold_before_warning(self):
        key, scene = self.ready()
        npc = next(iter(scene["actors"]))
        self.review(key, scene, self.result(scene, "hold"))
        event = dict(
            event_id="first-turn", session="game", epoch=1, combat_attack_ready=0
        )
        self.app.director_chat(npc, "player", event)
        # A fresh player statement changes the review fingerprint.
        self.app.store.message(npc, "player", "player", "I refuse to pay.")
        with patch(
            "roleweaver.director.evaluate", return_value=self.result(scene)
        ) as review:
            self.app.director_before_reply(
                npc,
                dict(event_id="first-turn", attack_ready=False),
                self.app.generations.get(npc, 0),
                dict(session="game", epoch=1),
            )
            review.assert_called_once()
        self.assertFalse(self.app.director_npc_context(npc)["holding"])
        choices, _ = self.app.live_combat_choices(
            npc, dict(event_id="first-turn", attack_ready=False)
        )
        self.assertIn("encounter:warn", [c["id"] for c in choices])

    def test_scene_exchange_is_scoped_and_bounded(self):
        key, scene = self.ready()
        with patch.object(self.app.pool, "submit") as submit:
            self.app.scene_exchange_tick()
            item = self.app.checkin
            self.assertIsNotNone(item)
            self.assertTrue(self.app.checkin_valid(item))
            self.assertEqual(submit.call_count, 1)
            self.app.scene_exchange_tick()
            self.assertEqual(submit.call_count, 1)
            scene["run"]["status"] = "paused"
            self.assertFalse(self.app.checkin_valid(item))
            scene["run"]["status"] = "active"
            scene["run"]["started"] += 1
            self.assertFalse(self.app.checkin_valid(item))

    def test_missing_permission_presence_and_busy_actor_prevent_speech(self):
        key, scene = self.ready()
        ids = list(scene["actors"])
        with patch.object(self.app.pool, "submit") as submit:
            self.app.busy.update(ids)
            self.app.scene_exchange_tick()
            self.app.busy.clear()
            self.app.director_presence[key]["players"] = []
            self.app.scene_exchange_tick()
            self.app.director_presence[key]["players"] = ["visitor-test"]
            self.app.action_config["npcs"][ids[0]]["nearby"]["receive"] = False
            self.app.scene_exchange_tick()
            submit.assert_not_called()

    def test_mechanical_payment_prose_is_filtered_but_counting_coins_is_not(self):
        for line in [
            "Confirm through the game.",
            "The video game must confirm the transfer.",
            "I need a native receipt.",
        ]:
            self.assertTrue(guardrails.screen_reply(line, {})[1])
        self.assertFalse(
            guardrails.screen_reply("Come closer and let me count the coins.", {})[1]
        )
