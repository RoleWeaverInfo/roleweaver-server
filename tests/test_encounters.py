"""General scene lifecycle, secret isolation and validated DM controls."""

import copy
import unittest
from tests import test_actions
from roleweaver import actions, backup, encounters, safeguards
from roleweaver.store import DEFAULT_NPC


class EncounterTests(unittest.TestCase):
    setUp = test_actions.ActionsTests.setUp
    tearDown = test_actions.ActionsTests.tearDown

    def scene(self, key="meeting"):
        return dict(
            id=key,
            name="Unexpected meeting",
            summary="DM synopsis secret",
            public_facts="The bridge is closed.",
            dm_notes="DM ONLY: hidden mastermind",
            boundaries="Allow refusal; no invented rewards.",
            location="",
            actors=[
                dict(
                    npc="mira",
                    role="Traveler",
                    knowledge="Lost a horse",
                    goal="Find help",
                )
            ],
            stages=[
                dict(id="opening", name="First meeting", situation="Ask for help"),
                dict(id="later", name="Later", situation="FUTURE secret"),
            ],
            outcomes=[
                dict(
                    id="helped", name="Help accepted", description="DM ONLY reward plan"
                )
            ],
        )

    def save(self, d):
        return self.app.save_encounter(d, self.app.encounter_revision)

    def control(self, op, key="meeting", **fields):
        return self.app.control_encounter(
            key, op, self.app.encounter_revision, **fields
        )

    def test_snapshot_context_excludes_secrets_and_other_roles(self):
        self.app.store.save(dict(DEFAULT_NPC, id="guard", name="Guard"))
        self.app.states["guard"] = dict(self.state)
        d = self.scene()
        d["actors"].append(
            dict(
                npc="guard",
                role="Watchman",
                knowledge="OTHER ACTOR secret",
                goal="Observe",
            )
        )
        self.save(d)
        self.control("start")
        context = self.app.encounter_context("mira")
        self.assertEqual(context["knowledge"], "Lost a horse")
        serialized = str(context)
        for private in ("DM ONLY", "OTHER ACTOR", "FUTURE", "synopsis"):
            self.assertNotIn(private, serialized)
        d["public_facts"] = "Changed for next run"
        self.save(d)
        self.assertEqual(
            self.app.encounter_context("mira")["public_facts"], "The bridge is closed."
        )
        self.assertEqual(
            safeguards.trusted_sources({"encounter": context}, [])[
                "authorized_encounter"
            ],
            context,
        )

    def test_manual_lifecycle_and_duplicate_start(self):
        self.save(self.scene())
        self.control("start")
        with self.assertRaises(ValueError):
            self.control("start")
        self.control("pause")
        with self.assertRaises(ValueError):
            self.control("stage", stage="later")
        self.control("resume")
        self.control("stage", stage="later")
        self.assertEqual(
            self.app.encounter_context("mira")["situation"], "FUTURE secret"
        )
        self.control("complete", outcome="helped")
        self.assertIsNone(self.app.encounter_for("mira"))
        # A recorded outcome only sends invalidation/stop commands, no rewards.
        self.assertTrue(
            all(
                '"kind": "controlled_stop"' in c[-1]
                for c in self.app.redis.commands
                if c[0] in ("RPUSH", "LPUSH")
            )
        )

    def test_conflict_revision_and_reservation(self):
        old = self.app.encounter_revision
        self.save(self.scene())
        with self.assertRaises(ValueError):
            self.app.save_encounter(self.scene(), old)
        self.save(self.scene("second"))
        self.control("start")
        with self.assertRaises(ValueError):
            self.control("start", "second")
        with self.assertRaises(ValueError):
            self.app.delete_npc("mira")
        with self.assertRaises(ValueError):
            self.app.delete_encounter("meeting", self.app.encounter_revision)

    def test_restart_and_game_session_change_pause(self):
        self.save(self.scene())
        self.control("start")
        self.app.init_encounters()
        self.assertEqual(self.app.encounter_context("mira")["status"], "paused")
        self.control("resume")
        self.app.encounter_session(dict(world="test", session="new"))
        self.assertEqual(self.app.encounter_context("mira")["status"], "paused")

    def test_backup_roundtrip_and_missing_actor_rejected(self):
        self.save(self.scene())
        self.control("start")
        data = self.app.backup_data()
        clean = backup.validate(data)
        self.assertEqual(clean["encounters"]["runs"]["meeting"]["status"], "active")
        backup.replace(self.app.store, clean)
        self.app.init_encounters()
        self.assertEqual(self.app.encounter_context("mira")["status"], "paused")
        bad = copy.deepcopy(data)
        bad["encounters"]["templates"]["meeting"]["actors"][0]["npc"] = "unknown"
        with self.assertRaises(ValueError):
            backup.validate(bad)
        old = copy.deepcopy(data)
        old["version"] = 11
        old.pop("encounters")
        self.assertEqual(
            backup.validate(old)["encounters"], dict(templates={}, runs={})
        )

    def test_retreat_requires_membership_permissions_and_new_bridge(self):
        self.app.action_config["destinations"]["inn"] = self.point
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, destinations=["inn"])
        )
        self.save(self.scene())
        self.control("start")

        def retreat(dest="inn"):
            return self.app.retreat_encounter_actor(
                "meeting", "mira", dest, self.app.encounter_revision
            )

        with self.assertRaises(ValueError):
            retreat()
        self.state.update(retreat_protocol=1, combat=1)
        with self.assertRaises(ValueError):
            retreat("unknown")
        retreat()
        self.assertEqual(self.app.redis.last()["action"], "retreat")
        self.assertEqual(self.app.action_jobs["mira"]["status"], "pending")
        self.state["possessed"] = 1
        with self.assertRaises(ValueError):
            retreat()

    def test_start_requires_correct_area_and_available_actor(self):
        self.app.action_config["destinations"]["inn"] = self.point
        d = self.scene()
        d["location"] = "inn"
        self.save(d)
        with self.assertRaises(ValueError):
            self.control("start")
        self.state.update(area_resref="inn", area_tag="inn", combat=1)
        with self.assertRaises(ValueError):
            self.control("start")
        self.state["combat"] = 0
        self.control("start")

    def test_definition_rejects_ambiguous_rows_and_invalid_shapes(self):
        d = self.scene()
        d["actors"] *= 2
        with self.assertRaises(ValueError):
            encounters.definition(d)
        d = self.scene()
        d["stages"] = []
        with self.assertRaises(ValueError):
            encounters.definition(d)
        d = self.scene()
        d["script"] = "arbitrary"
        with self.assertRaises(ValueError):
            encounters.definition(d)

    def test_spawn_cast_requires_dm_and_does_not_duplicate(self):
        self.save(self.scene())
        self.app.config["allow_dm_spawn"] = True
        with self.assertRaises(ValueError):
            self.app.spawn_encounter_cast("meeting", "dm", self.app.encounter_revision)
        self.app.dms["dm"] = dict(self.state, token="dm-token")
        result = self.app.spawn_encounter_cast(
            "meeting", "dm", self.app.encounter_revision
        )
        self.assertIn("Already connected", result["spawn_results"][0]["status"])
        self.app.states.clear()
        self.app.spawn_encounter_cast("meeting", "dm", self.app.encounter_revision)
        command = self.app.redis.last()
        self.assertEqual(command["kind"], "spawn_dm")
        self.assertEqual(command["blueprint"], "rw_custom")
        self.assertEqual(command["persistence"], "temporary")
        count = len(self.app.redis.commands)
        result = self.app.spawn_encounter_cast(
            "meeting", "dm", self.app.encounter_revision
        )
        self.assertIn("pending", result["spawn_results"][0]["status"])
        self.assertEqual(len(self.app.redis.commands), count)

    def test_spawn_cast_protects_live_encounters(self):
        self.save(self.scene())
        self.control("start")
        with self.assertRaises(ValueError):
            self.app.spawn_encounter_cast("meeting", "dm", self.app.encounter_revision)

    def test_spawn_partial_submission_reported(self):
        from unittest.mock import patch

        self.save(self.scene())
        self.app.config["allow_dm_spawn"] = True
        self.app.dms["dm"] = dict(self.state, token="dm-token")
        self.app.states.clear()
        with patch.object(
            self.app, "spawn_at_dm", side_effect=OSError("Redis unavailable")
        ):
            result = self.app.spawn_encounter_cast(
                "meeting", "dm", self.app.encounter_revision
            )
        self.assertIn("Not submitted", result["spawn_results"][0]["status"])
        self.assertNotIn("meeting", self.app.encounters["runs"])

    def test_reaction_defaults_and_strict_limits(self):
        self.assertFalse(encounters.definition(self.scene())["reaction"]["enabled"])
        for changes in (
            {"grace_seconds": 0},
            {"trigger_radius": 10},
            {"leave_radius": 5},
            {"attack": "yes"},
            {"warning": ""},
        ):
            with self.assertRaises(ValueError):
                encounters.reaction(dict(encounters.DEFAULT_REACTION, **changes))

    def test_reaction_requires_bridge_and_only_syncs_active_runs(self):
        import time

        d = self.scene()
        d["reaction"] = dict(encounters.DEFAULT_REACTION, enabled=True, attack=True)
        self.save(d)
        with self.assertRaises(ValueError):
            self.control("start")
        self.state["encounter_protocol"] = 2
        self.control("start")
        self.app.sync_encounter_reactions(dict(session="game"))
        cmd = self.app.redis.last()
        self.assertEqual(cmd["kind"], "encounter_arm")
        self.assertTrue(cmd["policy"]["attack"])
        self.assertEqual(cmd["actors"], [dict(npc="mira", epoch=1)])
        count = len(self.app.redis.commands)
        self.app.sync_encounter_reactions(dict(session="game"))
        self.assertEqual(len(self.app.redis.commands), count)
        self.control("pause")
        count = len(self.app.redis.commands)
        self.app.encounter_sync_at.clear()
        self.app.sync_encounter_reactions(dict(session="game"))
        self.assertEqual(len(self.app.redis.commands), count)

    def test_reaction_events_are_scoped_and_backed_up(self):
        self.save(self.scene())
        self.control("start")
        run = self.app.encounters["runs"]["meeting"]
        event = dict(
            world="test",
            session="game",
            encounter="meeting",
            token=str(run["started"]),
            status="warning",
            npc="mira",
        )
        old = len(run["events"])
        self.app.encounter_game_event(dict(event, token="stale"))
        self.assertEqual(len(run["events"]), old)
        self.app.encounter_game_event(event)
        self.assertIn(
            "Warning delivered", self.app.encounter_context("mira")["game_observation"]
        )
        snapshot = backup.validate(backup.export(self.app.store, self.app.salt))
        self.assertIn("reaction", snapshot["encounters"]["templates"]["meeting"])

    def test_combat_limits_migrate_old_definitions_and_validate(self):
        old = dict(encounters.DEFAULT_REACTION)
        old.pop("pursuit_radius")
        old.pop("retreat_hp_percent")
        migrated = encounters.reaction(old)
        self.assertEqual(migrated["pursuit_radius"], 20)
        self.assertEqual(migrated["retreat_hp_percent"], 25)
        for changes in (
            {"pursuit_radius": 9},
            {"pursuit_radius": 61},
            {"retreat_hp_percent": 91},
            {"retreat_hp_percent": True},
        ):
            with self.assertRaises(ValueError):
                encounters.reaction(dict(encounters.DEFAULT_REACTION, **changes))
        self.assertEqual(
            encounters.reaction(
                dict(
                    encounters.DEFAULT_REACTION, pursuit_radius=0, retreat_hp_percent=0
                )
            )["pursuit_radius"],
            0,
        )

    def test_combat_events_require_cast_membership(self):
        self.save(self.scene())
        self.control("start")
        run = self.app.encounters["runs"]["meeting"]
        event = dict(
            world="test",
            session="game",
            encounter="meeting",
            token=str(run["started"]),
            status="low_health",
            npc="unknown",
        )
        self.app.encounter_game_event(event)
        self.assertNotIn("meeting", self.app.encounter_observed)
        self.app.encounter_game_event(dict(event, npc="mira"))
        self.assertIn("mira: Low health", self.app.encounter_observed["meeting"])

    def test_end_releases_combat_monitor_without_forcing_game_combat_stop(self):
        self.save(self.scene())
        self.control("start")
        self.state["combat"] = 1
        self.control("cancel")
        self.assertEqual(self.app.redis.last()["kind"], "encounter_release")

    def test_restart_releases_orphaned_combat_monitor(self):
        self.save(self.scene())
        self.control("start")
        run = self.app.encounters["runs"]["meeting"]
        event = dict(
            combat_encounter="meeting", combat_token=str(run["started"]), session="game"
        )
        count = len(self.app.redis.commands)
        self.app.reconcile_encounter_combat("mira", event)
        self.assertEqual(len(self.app.redis.commands), count)
        self.app.init_encounters()
        self.app.reconcile_encounter_combat("mira", event)
        self.assertEqual(self.app.redis.last()["kind"], "encounter_release")
        self.assertEqual(self.app.redis.last()["token"], event["combat_token"])

    def test_rearmed_event_allows_repeated_warning_cycles_without_losing_run(self):
        self.save(self.scene())
        self.control("start")
        run = self.app.encounters["runs"]["meeting"]
        token = str(run["started"])
        event = dict(
            world="test", session="game", encounter="meeting", token=token, npc="mira"
        )
        for status in ("warning", "left", "rearmed", "warning", "attack", "rearmed"):
            self.app.encounter_game_event(dict(event, status=status))
        self.assertEqual(run["status"], "active")
        self.assertEqual(str(run["started"]), token)
        self.assertIn(
            "ready for another approach", self.app.encounter_observed["meeting"]
        )
        before = len(run["events"])
        self.app.encounter_game_event(dict(event, status="rearmed", token="old"))
        self.assertEqual(len(run["events"]), before)
