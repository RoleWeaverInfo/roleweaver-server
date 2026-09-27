"""Director isolation, permissions, stale work and offline recovery behavior."""

import copy
import hashlib
import time
import unittest
from unittest.mock import patch
from roleweaver import director
from roleweaver.live_director import initial
from tests import test_live_encounters as live_tests


class DirectorTests(unittest.TestCase):
    setUp = live_tests.LiveEncounterTests.setUp
    tearDown = live_tests.LiveEncounterTests.tearDown
    place = live_tests.LiveEncounterTests.place
    confirm = live_tests.LiveEncounterTests.confirm

    def prepare(self):
        self.app.config["provider"] = "openai-compatible"
        self.draft["reaction"].update(
            attack=True, combat_mode="conversation", combat_conditions="Negotiate first"
        )
        scene = self.place()
        self.confirm(scene)
        for n in scene["actors"]:
            self.app.states[n]["encounter_protocol"] = 4
        key = scene["run"]["template"]["id"]
        self.app.director_control(dict(id=key, operation="enable", direction=""))
        self.app.control_live(key, "start")
        self.app.director_runtime[key] = {}
        return key, scene

    def result(self, scene, operation="continue"):
        return dict(
            summary="The visitors are negotiating; no payment is confirmed.",
            phase="negotiating",
            reason="Consider their offer.",
            goals={next(iter(scene["actors"])): "Listen to a peaceful alternative."},
            operation=operation,
        )

    def review(self, key, scene, result, effect=None):
        context, fingerprint = self.app.director_context(key, scene)
        revision = scene["director"]["revision"]
        with patch(
            "roleweaver.director.evaluate", return_value=result, side_effect=effect
        ):
            self.app.director_review(
                key,
                scene["run"]["started"],
                revision,
                fingerprint,
                context,
                dict(self.app.config),
            )

    def test_schema_rejects_commands_and_unowned_actors(self):
        good = dict(
            summary="Waiting",
            phase="waiting",
            reason="No player",
            goals={},
            operation="continue",
        )
        for change in (
            dict(operation="attack"),
            dict(goals={"outsider": "attack"}),
            dict(script="bad"),
            dict(summary=""),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                director.validate(dict(good, **change), {"mira"})

    def test_game_ready_reply_releases_review_hold_and_exposes_attack(self):
        key, scene = self.prepare()
        npc = next(iter(scene["actors"]))
        self.review(key, scene, self.result(scene, "hold"))
        self.assertTrue(self.app.director_npc_context(npc)["holding"])
        event = dict(event_id="game:2", session="game", epoch=1, combat_attack_ready=1)
        self.app.director_chat(npc, "private-player", event)

        def review(config, context):
            readiness = context["actors"][npc]["last_player_reply"]
            self.assertTrue(readiness["attack_ready"])
            self.assertTrue(readiness["participant"].startswith("visitor-"))
            self.assertNotIn("private-player", str(context))
            return dict(
                self.result(scene),
                reason="Game confirms the grace period and later reply.",
            )

        self.review(key, scene, None, review)
        self.assertFalse(self.app.director_npc_context(npc)["holding"])
        choices, command = self.app.live_combat_choices(
            npc, dict(event_id="game:2", attack_ready=True)
        )
        self.assertIn("encounter:attack", [c["id"] for c in choices])
        self.assertEqual(command["combat_event"], "game:2")
        choices, _ = self.app.live_combat_choices(
            npc, dict(event_id="game:3", attack_ready=False)
        )
        self.assertNotIn("encounter:attack", [c["id"] for c in choices])
        self.app.director_control(dict(id=key, operation="pause", direction=""))
        self.assertEqual(
            self.app.live_combat_choices(
                npc, dict(event_id="game:4", attack_ready=True)
            ),
            ([], {}),
        )

    def test_stale_game_readiness_is_not_director_evidence(self):
        key, scene = self.prepare()
        npc = next(iter(scene["actors"]))
        event = dict(event_id="game:2", session="game", epoch=1, combat_attack_ready=1)
        self.app.director_chat(npc, "p", dict(event, session="old-game"))
        context, _ = self.app.director_context(key, scene)
        self.assertIsNone(context["actors"][npc]["last_player_reply"])

        self.app.director_chat(npc, "p", event)
        self.app.director_turns[npc]["seen"] -= 121
        context, _ = self.app.director_context(key, scene)
        self.assertIsNone(context["actors"][npc]["last_player_reply"])
        self.app.director_chat(npc, "p", event)
        self.app.control_live(key, "pause")
        self.app.control_live(key, "start")
        context, _ = self.app.director_context(key, scene)
        self.assertIsNone(context["actors"][npc]["last_player_reply"])

    def test_priority_review_runs_before_same_reply_despite_normal_cooldown(self):
        key, scene = self.prepare()
        npc = next(iter(scene["actors"]))
        self.review(key, scene, self.result(scene, "hold"))
        self.app.director_last_at = time.monotonic()
        self.app.director_runtime[key]["next"] = time.monotonic() + 10
        self.app.director_chat(
            npc,
            "p",
            dict(event_id="game:ready", session="game", epoch=1, combat_attack_ready=1),
        )
        calls = []

        def evaluate(config, context):
            calls.append("director")
            return self.result(scene)

        def reply(config, profile, memories, history):
            calls.append("reply")
            self.assertFalse(profile["encounter"]["direction"]["holding"])
            choices = [a["id"] for a in profile["controlled_actions"]]
            self.assertIn("encounter:attack", choices)
            self.assertNotIn("encounter:warn", choices)
            return '{"speech":"Defend yourself.","action":"encounter:attack"}'

        with (
            patch("roleweaver.director.evaluate", side_effect=evaluate),
            patch("roleweaver.provider.reply", side_effect=reply),
        ):
            self.app.generate(
                npc,
                "p",
                dict(
                    self.app.store.get(npc),
                    _combat_turn=dict(event_id="game:ready", attack_ready=True),
                ),
                self.app.generations[npc],
                dict(self.app.states[npc]),
                "pc",
                speech="I refuse and I am staying",
            )
        self.assertEqual(calls, ["director", "reply"])
        self.assertEqual(self.app.redis.last()["encounter_choice"], "encounter:attack")

    def test_priority_review_respects_pause_backoff_busy_and_budget(self):
        key, scene = self.prepare()
        npc = next(iter(scene["actors"]))
        self.app.director_chat(
            npc,
            "p",
            dict(event_id="game:ready", session="game", epoch=1, combat_attack_ready=1),
        )

        def attempt():
            self.app.director_before_reply(
                npc,
                dict(event_id="game:ready", attack_ready=True),
                self.app.generations[npc],
                self.app.states[npc],
            )

        with patch("roleweaver.director.evaluate") as evaluate:
            scene["director"]["paused"] = True
            attempt()
            scene["director"]["paused"] = False
            self.app.director_busy = True
            attempt()
            self.app.director_busy = False
            self.app.director_runtime[key]["retry_after"] = time.monotonic() + 60
            attempt()
            self.app.director_runtime[key]["retry_after"] = 0
            scene["director"]["reviews"] = 60
            attempt()
            evaluate.assert_not_called()

    def test_busy_director_queues_priority_without_waiting_normal_cooldown(self):
        key, scene = self.prepare()
        npc = next(iter(scene["actors"]))
        self.app.director_chat(
            npc,
            "p",
            dict(event_id="game:ready", session="game", epoch=1, combat_attack_ready=1),
        )
        self.app.director_busy = True
        self.app.director_before_reply(
            npc,
            dict(event_id="game:ready", attack_ready=True),
            self.app.generations[npc],
            self.app.states[npc],
        )
        self.assertTrue(self.app.director_runtime[key]["priority"])
        self.app.director_busy = False
        self.app.director_last_at = time.monotonic()
        self.app.director_runtime[key]["next"] = time.monotonic() + 10
        with patch.object(self.app.pool, "submit") as submit:
            self.app.director_tick()
        submit.assert_called_once()
        self.assertNotIn("priority", self.app.director_runtime[key])

    def test_scoped_transcript_and_hashed_participants(self):
        key, scene = self.prepare()
        npc = next(iter(scene["actors"]))
        self.app.store.message("mira", "outside", "player", "PRIVATE OUTSIDE SCENE")
        self.app.store.message(npc, "secret-player-identity", "player", "I offer help")
        context, _ = self.app.director_context(key, scene)
        self.assertEqual(len(context["dialogue"]), 1)
        self.assertNotIn("secret-player-identity", str(context))
        self.assertNotIn("PRIVATE OUTSIDE SCENE", str(context))
        self.assertEqual(context["nearby_players"], None)

    def test_guidance_only_and_pause_invalidates_pending_work(self):
        key, scene = self.prepare()
        before = len(self.app.redis.commands)
        self.review(key, scene, self.result(scene))
        self.assertEqual(len(self.app.redis.commands), before)
        npc = next(iter(scene["actors"]))
        self.assertIn("peaceful", self.app.director_npc_context(npc)["goal"])

        def paused(*args):
            self.app.director_control(dict(id=key, operation="pause", direction=""))
            return dict(self.result(scene), summary="SHOULD NOT APPLY")

        self.review(key, scene, None, paused)
        self.assertNotEqual(scene["director"]["summary"], "SHOULD NOT APPLY")
        self.assertEqual(self.app.states[npc]["mode"], "auto")
        self.assertEqual(
            self.app.live_combat_choices(npc, dict(event_id="1", attack_ready=True)),
            ([], {}),
        )

    def test_new_dialogue_discards_stale_result(self):
        key, scene = self.prepare()

        def more_dialogue(*args):
            self.app.store.message(
                next(iter(scene["actors"])), "p", "player", "Wait, a different offer"
            )
            return self.result(scene)

        self.review(key, scene, None, more_dialogue)
        self.assertEqual(scene["director"]["summary"], "")

    def test_resolution_waits_for_game_confirmation(self):
        key, scene = self.prepare()
        self.review(key, scene, self.result(scene, "resolve"))
        self.assertFalse(scene["director"]["resolved"])
        command = self.app.redis.last()
        self.assertEqual(command["kind"], "encounter_end")
        self.assertEqual(command["live_owner"], scene["owner"])
        self.app.live_game_event(
            dict(
                kind="encounter_event",
                encounter=key,
                world="test",
                session="game",
                token=str(scene["run"]["started"]),
                npc=next(iter(scene["actors"])),
                status="director_finished",
            )
        )
        self.assertTrue(scene["director"]["resolved"])

    def test_failure_holds_combat_and_backs_off(self):
        key, scene = self.prepare()
        self.review(key, scene, None, RuntimeError("provider secret must not leak"))
        self.assertNotIn("secret", scene["director"]["error"])
        self.assertGreater(
            self.app.director_runtime[key]["next"], time.monotonic() + 55
        )
        self.assertTrue(
            self.app.director_npc_context(next(iter(scene["actors"])))["holding"]
        )
        self.assertFalse(self.app.director_busy)

    def test_presence_rejects_old_activation_and_matches_transcript_alias(self):
        key, scene = self.prepare()
        event = dict(
            encounter=key,
            world="test",
            session="game",
            token="old",
            npc=next(iter(scene["actors"])),
            players=["cdkey:Name"],
        )
        self.app.director_observe(event)
        self.assertNotIn(key, self.app.director_presence)
        event["token"] = str(scene["run"]["started"])
        self.app.director_observe(event)
        identity = hashlib.sha256((self.app.salt + "cdkey:Name").encode()).hexdigest()[
            :24
        ]
        self.app.store.message(event["npc"], identity, "player", "Hello")
        context, _ = self.app.director_context(key, scene)
        self.assertEqual(
            context["nearby_players"], [context["dialogue"][0]["participant"]]
        )
        self.assertNotIn("cdkey", str(context))

    def test_idle_scene_does_not_request_and_budget_is_bounded(self):
        key, scene = self.prepare()
        _, fingerprint = self.app.director_context(key, scene)
        self.app.director_runtime[key]["fingerprint"] = fingerprint
        with patch.object(self.app.pool, "submit") as submit:
            self.app.director_tick()
            submit.assert_not_called()
            self.app.director_poll_at = 0
            self.app.director_runtime[key].clear()
            scene["director"]["reviews"] = 60
            self.app.director_tick()
            submit.assert_not_called()
        self.assertTrue(scene["director"]["paused"])
