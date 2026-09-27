"""Persistent AI direction: approval, recovery, isolation and completion authority."""

import copy
import json
import time
import unittest
from unittest.mock import patch
from tests import test_encounters
from roleweaver import encounters, director, backup


class PersistentDirectorTests(unittest.TestCase):
    setUp = test_encounters.EncounterTests.setUp
    tearDown = test_encounters.EncounterTests.tearDown
    scene = test_encounters.EncounterTests.scene
    save = test_encounters.EncounterTests.save
    control = test_encounters.EncounterTests.control

    def prepare(self, trigger=False):
        self.app.config["provider"] = "openai-compatible"
        self.state["encounter_protocol"] = 6
        d = self.scene()
        d["automation"] = dict(
            enabled=True, resume_after_restart=True, repeat_after_restart=False
        )
        d["reaction"] = dict(encounters.DEFAULT_REACTION, enabled=trigger)
        self.save(d)
        self.control("start")
        return self.app.encounters["runs"]["meeting"]

    def hello(self, session="game"):
        self.app.encounter_session(dict(world="test", session=session))

    def review(self, operation="continue", stage="opening", outcome=""):
        scene = self.app.director_scenes()["meeting"]
        context, fingerprint = self.app.director_context("meeting", scene)
        self.app.director_runtime["meeting"] = {}
        result = dict(
            summary="Waiting for confirmed events.",
            phase="waiting",
            reason="Observed conditions.",
            goals={},
            operation=operation,
            stage=stage,
            outcome=outcome,
        )
        with patch("roleweaver.director.evaluate", return_value=result):
            self.app.director_review(
                "meeting",
                scene["run"]["started"],
                scene["director"]["revision"],
                fingerprint,
                context,
                dict(self.app.config),
            )
        return context

    def test_save_does_not_activate_arm_reserves_and_waits_without_dm(self):
        self.prepare()
        self.control("cancel")
        self.app.states.clear()
        self.control("arm")
        run = self.app.encounters["runs"]["meeting"]
        self.assertEqual(run["status"], "waiting")
        self.assertIs(self.app.encounter_for("mira"), run)
        self.hello("new")
        self.assertEqual(run["status"], "waiting")
        self.assertTrue(run["recovery_reason"])
        self.app.states["mira"] = dict(self.state, session="new", seen=time.monotonic())
        self.hello("new")
        self.assertEqual(run["status"], "active")
        self.assertEqual(self.app.dms, {})
        self.assertFalse(any("spawn" in str(c) for c in self.app.redis.commands))

    def test_new_session_keeps_stage_memory_and_waits_for_current_actors(self):
        run = self.prepare()
        self.control("stage", stage="later")
        run = self.app.encounters["runs"]["meeting"]
        old = run["owner"]
        token = run["started"]
        self.app.store.message("mira", "visitor", "player", "Remember the oak tree.")
        self.hello("new")
        self.assertEqual(run["status"], "waiting")
        self.assertNotEqual(run["owner"], old)
        self.assertNotEqual(run["started"], token)
        self.state.update(session="new", seen=time.monotonic())
        self.hello("new")
        self.assertEqual(run["status"], "active")
        self.assertEqual(run["stage"], "later")
        self.assertEqual(
            self.app.store.db.execute("SELECT count(*) FROM messages").fetchone()[0], 1
        )

    def test_companion_restart_and_explicit_pause(self):
        self.prepare()
        self.app.init_encounters()
        run = self.app.encounters["runs"]["meeting"]
        self.assertEqual(run["status"], "waiting")
        self.hello()
        self.assertEqual(run["status"], "active")
        self.control("pause")
        self.app.init_encounters()
        self.state["session"] = "new"
        self.hello("new")
        self.assertEqual(self.app.encounters["runs"]["meeting"]["status"], "paused")

    def test_director_pause_survives_restart(self):
        run = self.prepare()
        self.app.persistent_director_control(
            dict(id="meeting", operation="pause", direction="")
        )
        self.state["session"] = "new"
        self.hello("new")
        self.assertTrue(run["director"]["paused"])
        self.assertTrue(self.app.director_npc_context("mira")["holding"])

    def test_completion_only_repeats_after_game_restart_if_opted_in(self):
        self.prepare()
        self.review("resolve", outcome="helped")
        run = self.app.encounters["runs"]["meeting"]
        self.assertEqual(run["status"], "completed")
        self.state["session"] = "new"
        self.hello("new")
        self.assertEqual(run["status"], "completed")
        run["template"]["automation"]["repeat_after_restart"] = True
        self.hello("new")
        self.assertEqual(run["status"], "active")
        self.assertEqual(run["outcome"], "")

    def test_reaction_resolution_waits_for_game_and_scoped_ack(self):
        run = self.prepare(trigger=True)
        self.review("resolve", outcome="helped")
        self.assertEqual(run["status"], "active")
        cmd = self.app.redis.last()
        self.assertEqual(cmd["kind"], "encounter_end")
        self.assertEqual(cmd["persistent_owner"], run["owner"])
        self.assertNotIn("live_owner", cmd)
        self.app.director_command_result(dict(cmd, token="stale"), True)
        self.assertEqual(run["status"], "active")
        self.app.director_command_result(cmd, True)
        self.assertEqual(run["status"], "completed")

    def test_stage_progression_is_validated_and_private_notes_omitted(self):
        run = self.prepare()
        context = self.review("stage", stage="later")
        self.assertEqual(run["stage"], "later")
        self.assertNotIn("hidden mastermind", str(context))
        self.assertNotIn("DM synopsis secret", str(context))
        self.review("stage", stage="unapproved")
        self.assertEqual(run["stage"], "later")
        self.assertTrue(run["director"]["error"])

    def test_backup_roundtrip_and_legacy_defaults(self):
        self.prepare()
        self.review()
        data = backup.validate(self.app.backup_data())
        self.assertTrue(data["encounters"]["runs"]["meeting"]["director"]["enabled"])
        legacy = encounters.definition(self.scene())
        self.assertFalse(legacy["automation"]["enabled"])
        self.assertFalse(legacy["checks"]["enabled"])

    def test_persistent_director_and_live_journals_are_separate(self):
        run = self.prepare()
        with patch.object(
            self.app, "persist_live", side_effect=AssertionError("wrong journal")
        ):
            self.review()
        self.assertTrue(run["director"]["summary"])
        self.assertFalse(self.app.live_scenes)

    def test_authoring_proposal_never_arms_or_expands_combat(self):
        d = self.scene()
        result = dict(summary="A meeting", limitations=[], draft=d)
        with patch("roleweaver.dm_assistant.request", return_value=result):
            proposal = self.app.persistent_assistant(
                dict(instruction="Build a meeting", allow_combat=False)
            )
        self.assertFalse(proposal["draft"]["automation"]["enabled"])
        self.assertFalse(self.app.encounters["runs"])
        self.assertFalse(self.app.encounters["templates"])
        self.assertFalse(self.app.redis.commands)

    def test_combat_command_uses_persistent_authority(self):
        run = self.prepare(trigger=True)
        run["template"]["reaction"].update(
            attack=True,
            combat_mode="conversation",
            combat_conditions="Warn before fighting",
        )
        self.review()
        choices, cmd = self.app.live_combat_choices(
            "mira", dict(event_id="game:2", attack_ready=True)
        )
        self.assertIn("encounter:attack", [c["id"] for c in choices])
        self.assertEqual(cmd["persistent_owner"], run["owner"])

    def test_old_protocol_cannot_recover(self):
        run = self.prepare()
        self.state.update(session="new", encounter_protocol=5)
        self.hello("new")
        self.assertEqual(run["status"], "waiting")
        self.assertIn("protocol 6", run["recovery_reason"])

    def test_initial_arm_waits_even_when_later_restart_recovery_disabled(self):
        self.prepare()
        self.control("cancel")
        self.app.encounters["templates"]["meeting"]["automation"][
            "resume_after_restart"
        ] = False
        self.app.states.clear()
        self.control("arm")
        run = self.app.encounters["runs"]["meeting"]
        self.hello()
        self.app.states["mira"] = self.state
        self.hello()
        self.assertEqual(run["status"], "active")
        self.state["session"] = "new"
        self.hello("new")
        self.assertEqual(run["status"], "paused")

    def test_manual_pause_invalidates_an_inflight_decision(self):
        self.prepare()
        scene = self.app.director_scenes()["meeting"]
        context, fingerprint = self.app.director_context("meeting", scene)
        result = dict(
            summary="Old result",
            phase="waiting",
            reason="stale",
            goals={},
            operation="continue",
            stage="opening",
            outcome="",
        )
        revision = scene["director"]["revision"]

        def during_request(*args):
            self.control("pause")
            self.control("resume")
            return result

        with patch("roleweaver.director.evaluate", side_effect=during_request):
            self.app.director_review(
                "meeting",
                scene["run"]["started"],
                revision,
                fingerprint,
                context,
                dict(self.app.config),
            )
        self.assertNotEqual(
            self.app.encounters["runs"]["meeting"]["director"]["summary"], "Old result"
        )


if __name__ == "__main__":
    unittest.main()
