import time
import unittest
from unittest.mock import patch
from roleweaver import actions, village
from tests import test_actions


class VillageTests(unittest.TestCase):
    setUp = test_actions.ActionsTests.setUp
    tearDown = test_actions.ActionsTests.tearDown

    def ready(self):
        self.app.action_config["destinations"]["inn"] = self.point
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                home="inn",
                village=dict(village.DEFAULT, enabled=True),
            ),
        )
        self.state.update(
            village_protocol=1,
            area="Inn Name",
            area_resref="inn",
            area_tag="inn",
            x=1.0,
            y=2.0,
        )
        self.app.village_runtime["mira"] = dict(session="game", next=0, steps=0)

    def tick(self, choice="wander"):
        with patch("roleweaver.village.random.choice", return_value=choice):
            self.app.village_tick("mira", self.state)

    def test_defaults_validation_and_home(self):
        self.assertFalse(village.policy()["enabled"])
        for change in (
            dict(radius=True),
            dict(radius=13),
            dict(activity="fast"),
            dict(visits=1),
        ):
            with self.assertRaises(ValueError):
                village.policy(dict(village.DEFAULT, **change))
        with self.assertRaises(ValueError):
            self.app.save_action_policy(
                "mira",
                dict(
                    actions.DEFAULT_POLICY,
                    enabled=True,
                    village=dict(village.DEFAULT, enabled=True),
                ),
            )

    def test_dispatch_and_no_replay(self):
        self.ready()
        self.tick()
        cmd = self.app.redis.last()
        self.assertEqual(cmd["action"], "village")
        self.assertEqual(cmd["village_home"], self.point)
        self.assertEqual(cmd["village_radius"], 8)
        count = len(self.app.redis.commands)
        self.tick()
        self.assertEqual(len(self.app.redis.commands), count)

    def test_interruption_priority(self):
        for field, value in (
            ("mode", "paused"),
            ("combat", 1),
            ("possessed", 1),
            ("dead", 1),
            ("conversation_active", 1),
            ("area_resref", "other"),
            ("village_protocol", 0),
        ):
            with self.subTest(field=field):
                self.ready()
                old = self.state.get(field)
                self.state[field] = value
                count = len(self.app.redis.commands)
                self.tick()
                self.assertEqual(len(self.app.redis.commands), count)
                self.state[field] = old

    def test_patrol_and_encounter_priority(self):
        self.ready()
        self.app.action_config["npcs"]["mira"]["patrol"] = {"enabled": True}
        self.tick()
        self.assertNotIn("mira", self.app.action_jobs)
        self.app.action_config["npcs"]["mira"].pop("patrol")
        with patch.object(self.app, "encounter_for", return_value="scene"):
            self.tick()
            self.assertNotIn("mira", self.app.action_jobs)

    def test_rest_no_request_and_home_cycle(self):
        self.ready()
        self.tick("rest")
        self.assertNotIn("mira", self.app.action_jobs)
        self.app.village_runtime["mira"].update(next=0, steps=3)
        self.state["x"] = 5
        with patch(
            "roleweaver.village.random.choice", side_effect=lambda options: options[0]
        ):
            self.app.village_tick("mira", self.state)
        self.assertEqual(self.app.redis.last()["target"], "home")

    def test_stop_halts_until_saved(self):
        self.ready()
        self.app.stop_action("mira")
        count = len(self.app.redis.commands)
        self.tick()
        self.assertEqual(len(self.app.redis.commands), count)
        p = self.app.action_config["npcs"]["mira"]
        self.app.save_action_policy("mira", p)
        self.assertNotIn("mira", self.app.village_runtime)

    def test_session_change_and_boundary(self):
        self.ready()
        self.state["session"] = "new"
        self.tick()
        self.assertNotIn("mira", self.app.action_jobs)
        self.app.village_runtime["mira"]["next"] = 0
        self.state["x"] = 99
        self.tick()
        self.assertNotIn("mira", self.app.action_jobs)

    def test_movement_context_distinguishes_distance_from_permission(self):
        self.ready()
        self.app.action_config["npcs"]["mira"]["nearby"].update(
            talk=True, approach=True, radius=8
        )
        self.state["nearby_targets"] = {
            "v1": dict(peer="guard", label="Guard", distance=11)
        }
        context = self.app.movement_context("mira")
        self.assertTrue(context["initiate_npc_conversations"])
        self.assertEqual(
            context["visible_npc_visits"][0]["status"],
            "Outside permitted visit distance",
        )

    def test_first_activity_is_walk_and_rest_is_followed_by_walk(self):
        self.ready()
        with patch(
            "roleweaver.village.random.choice", side_effect=lambda options: options[-1]
        ):
            self.app.village_tick("mira", self.state)
        self.assertEqual(self.app.redis.last()["target"], "wander")
        self.app.action_jobs["mira"]["status"] = "completed"
        self.app.village_runtime["mira"]["next"] = 0
        self.app.action_last["mira"] = 0
        self.tick("rest")
        self.app.village_runtime["mira"]["next"] = 0
        self.tick("rest")
        self.assertTrue(self.app.village_runtime["mira"]["need_walk"])
        self.app.village_runtime["mira"]["next"] = 0
        with patch(
            "roleweaver.village.random.choice", side_effect=lambda options: options[-1]
        ):
            self.app.village_tick("mira", self.state)
        self.assertEqual(self.app.redis.last()["target"], "wander")

    def test_testing_cooldown_is_opt_in(self):
        self.ready()
        self.assertEqual(self.app.visit_cooldown("mira"), 300)
        self.app.action_config["npcs"]["mira"]["village"]["activity"] = "testing"
        self.assertEqual(self.app.visit_cooldown("mira"), 20)
        self.assertEqual(village.INTERVALS["testing"], (5, 5))

    def test_waits_for_approaching_visitor(self):
        self.ready()
        self.app.action_jobs["other"] = dict(
            visit_peer="mira", status="running", started=time.monotonic()
        )
        self.tick()
        self.assertNotIn("mira", self.app.action_jobs)
        self.assertIn("approaching", self.app.village_runtime["mira"]["status"])
