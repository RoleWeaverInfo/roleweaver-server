"""Conversation combat is opt-in, scene-scoped and uses game-supplied chat facts."""

import copy
import unittest
from roleweaver.encounters import reaction, DEFAULT_REACTION
from roleweaver import dm_assistant
from tests import test_live_encounters as live_tests


class ConversationCombatTests(unittest.TestCase):
    setUp = live_tests.LiveEncounterTests.setUp
    tearDown = live_tests.LiveEncounterTests.tearDown
    place = live_tests.LiveEncounterTests.place
    confirm = live_tests.LiveEncounterTests.confirm

    def test_opening_is_bounded_and_legacy_scenes_get_a_default(self):
        old = dict(DEFAULT_REACTION)
        old.pop("opening")
        self.assertEqual(reaction(old)["opening"], DEFAULT_REACTION["opening"])
        for value in ("", "x" * 501, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                reaction(dict(DEFAULT_REACTION, opening=value))
        self.assertEqual(
            reaction(dict(DEFAULT_REACTION, opening="Stop there, traveler."))[
                "opening"
            ],
            "Stop there, traveler.",
        )

    def test_old_policy_and_explicit_permission(self):
        old = {k: v for k, v in DEFAULT_REACTION.items() if not k.startswith("combat_")}
        self.assertEqual(reaction(old)["combat_mode"], "timed")
        for change in (
            {"attack": False},
            {"enabled": False},
            {"combat_conditions": ""},
            {"combat_mode": "anything"},
        ):
            policy = dict(
                DEFAULT_REACTION,
                enabled=True,
                attack=True,
                combat_mode="conversation",
                combat_conditions="Warn after refusal",
            )
            policy.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                reaction(policy)

    def test_only_active_spokesperson_current_bridge_gets_choices(self):
        self.draft["reaction"].update(
            attack=True,
            combat_mode="conversation",
            combat_conditions="Warn then attack after repeated refusal",
        )
        scene = self.place()
        self.confirm(scene)
        first, other = scene["actors"]
        turn = dict(event_id="game:42", attack_ready=True)
        self.assertEqual(self.app.live_combat_choices(first, turn), ([], {}))
        for n in scene["actors"]:
            self.app.states[n]["encounter_protocol"] = 3
        self.app.control_live(scene["run"]["template"]["id"], "start")
        choices, command = self.app.live_combat_choices(first, turn)
        self.assertIn("encounter:attack", [a["id"] for a in choices])
        self.assertEqual(command["combat_event"], "game:42")
        self.assertEqual(command["live_owner"], scene["owner"])
        self.assertEqual(self.app.live_combat_choices(other, turn), ([], {}))
        self.assertEqual(self.app.live_combat_choices(first, {}), ([], {}))
        choices, _ = self.app.live_combat_choices(
            first, dict(event_id="game:43", attack_ready=False)
        )
        self.assertNotIn("encounter:attack", [a["id"] for a in choices])
        scene["run"]["status"] = "paused"
        self.assertEqual(self.app.live_combat_choices(first, turn), ([], {}))

    def test_start_rejects_old_bridge(self):
        self.draft["reaction"].update(
            attack=True,
            combat_mode="conversation",
            combat_conditions="Refusal after warning",
        )
        scene = self.place()
        self.confirm(scene)
        with self.assertRaisesRegex(ValueError, "updated game scripts"):
            self.app.control_live(scene["run"]["template"]["id"], "start")
        self.assertEqual(scene["run"]["status"], "staged")

    def test_assistant_cannot_grant_its_own_permission(self):
        draft = {
            k: self.draft[k]
            for k in (
                "name",
                "profile",
                "count",
                "public_facts",
                "goal",
                "boundaries",
                "reaction",
                "repeat",
            )
        }
        draft = copy.deepcopy(draft)
        draft["reaction"].update(
            attack=True,
            combat_mode="conversation",
            combat_conditions="Repeated refusal after warning",
        )
        value = dict(summary="Robber", limitations=[], draft=draft)
        with self.assertRaises(ValueError):
            dm_assistant.validate(value, {"mira"}, False)
        self.assertEqual(
            dm_assistant.validate(value, {"mira"}, True)["draft"]["reaction"][
                "combat_mode"
            ],
            "conversation",
        )
