"""The assistant proposes data and never gets direct spawning authority."""

import copy
import unittest
from unittest.mock import patch
from roleweaver import dm_assistant
from roleweaver.encounters import DEFAULT_REACTION
from tests import test_live_encounters


class AssistantTests(unittest.TestCase):
    setUp = test_live_encounters.LiveEncounterTests.setUp
    tearDown = test_live_encounters.LiveEncounterTests.tearDown

    def proposal(self):
        return dict(
            summary="Two travelers request help.",
            limitations=[],
            draft=dict(
                name="Travelers",
                profile="mira",
                count=2,
                public_facts="The road is muddy.",
                goal="Ask for directions.",
                boundaries="Allow refusal.",
                repeat=False,
                reaction=dict(DEFAULT_REACTION),
            ),
        )

    def test_proposal_never_mutates_world(self):
        before = copy.deepcopy(self.app.action_config)
        with patch("roleweaver.dm_assistant.generate", return_value=self.proposal()):
            result = self.app.assist_live(
                dict(
                    instruction="Two travelers ask for help",
                    scene="",
                    allow_combat=False,
                )
            )
        self.assertEqual(result["draft"]["count"], 2)
        self.assertEqual(self.app.redis.commands, [])
        self.assertEqual(self.app.action_config, before)
        self.assertEqual(self.app.live_scenes, {})
        self.assertFalse(self.app.live_assistant_busy)

    def test_rejects_attack_without_permission_and_invalid_outputs(self):
        bad = self.proposal()
        bad["draft"]["reaction"].update(enabled=True, attack=True)
        with self.assertRaises(ValueError):
            dm_assistant.validate(bad, {"mira"}, False)
        self.assertTrue(
            dm_assistant.validate(bad, {"mira"}, True)["draft"]["reaction"]["attack"]
        )
        for change in (
            dict(count=99),
            dict(count=True),
            dict(profile="invented"),
            dict(profile=[]),
            dict(repeat="yes"),
            dict(script="ExecuteScript"),
        ):
            value = self.proposal()
            value["draft"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                dm_assistant.validate(value, {"mira"})

    def test_review_operation_allowlist(self):
        for op in ("none", "start", "pause", "cleanup"):
            self.assertEqual(
                dm_assistant.validate(
                    dict(summary="Review", limitations=[], operation=op),
                    {},
                    review=True,
                )["operation"],
                op,
            )
        with self.assertRaises(ValueError):
            dm_assistant.validate(
                dict(summary="Review", limitations=[], operation="attack"),
                {},
                review=True,
            )

    def test_provider_error_releases_busy(self):
        with patch(
            "roleweaver.dm_assistant.generate", side_effect=ValueError("No response")
        ):
            with self.assertRaises(ValueError):
                self.app.assist_live(
                    dict(instruction="Help", scene="", allow_combat=False)
                )
        self.assertFalse(self.app.live_assistant_busy)
        self.assertEqual(self.app.redis.commands, [])

    def test_unknown_scene_and_busy_rejected(self):
        with self.assertRaises(ValueError):
            self.app.assist_live(
                dict(instruction="Help", scene="missing", allow_combat=False)
            )
        self.app.live_assistant_busy = True
        with self.assertRaises(ValueError):
            self.app.assist_live(dict(instruction="Help", scene="", allow_combat=False))
