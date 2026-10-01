"""Encounter decisions must remain exact, permitted operations."""

import unittest
from unittest.mock import patch
from roleweaver import encounter_intent


class EncounterIntentTests(unittest.TestCase):
    def test_valid_choices_and_untrusted_text_are_passed_as_data(self):
        choices = [
            {"id": n, "description": n}
            for n in ("encounter:warn", "payment:100", "payment:75", "exchange:player")
        ]
        with patch(
            "roleweaver.encounter_intent.request",
            return_value={"action": "payment:100"},
        ) as request:
            self.assertEqual(
                encounter_intent.choose({}, "I will pay", [], {}, {}, choices),
                "payment:100",
            )
        context = request.call_args.args[2]
        self.assertEqual(context["speech"], "I will pay")
        self.assertNotIn("exchange:player", [a["id"] for a in context["choices"]])

    def test_unavailable_attack_and_malformed_choices_fail_closed(self):
        for result in (
            {"action": "encounter:attack"},
            {"action": 1},
            {"action": "", "extra": True},
        ):
            with (
                self.subTest(result=result),
                patch("roleweaver.encounter_intent.request", return_value=result),
            ):
                with self.assertRaises(ValueError):
                    encounter_intent.choose(
                        {}, "Fight", [], {}, {}, [{"id": "encounter:warn"}]
                    )

    def test_no_permission_does_not_call_model(self):
        with patch("roleweaver.encounter_intent.request") as request:
            self.assertEqual(
                encounter_intent.choose(
                    {}, "Fight", [], {}, {}, [{"id": "gesture:wave"}]
                ),
                "",
            )
            request.assert_not_called()

class DirectorCorrectionTests(unittest.TestCase):
    def test_stage_mismatch_retries_without_applying_invalid_decision(self):
        from roleweaver import director
        context = {"actors": {}, "progression": {"current":"first", "stages":[{"id":"first"},{"id":"second"}], "outcomes":[]}}
        bad = dict(summary="Waiting", phase="negotiating", reason="Advance", goals={}, operation="continue", stage="second", outcome="")
        with patch("roleweaver.director.request", side_effect=[bad, dict(bad, operation="stage")]) as request:
            self.assertEqual(director.evaluate({},context)["operation"],"stage")
            self.assertEqual(request.call_count,2)
        with patch("roleweaver.director.request", return_value=bad) as request:
            with self.assertRaises(ValueError): director.evaluate({},context)
            self.assertEqual(request.call_count,2)
