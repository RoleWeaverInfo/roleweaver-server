"""Patrol must never infer completion or override player/DM control."""

import time
from tests.test_actions import ActionsTests
from roleweaver import actions, patrol


class PatrolTests(ActionsTests):
    def prepare(self):
        self.app.action_config["destinations"]["inn"] = self.point
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, destinations=["inn"])
        )
        self.app.save_patrol(
            "mira", dict(patrol.DEFAULT, enabled=True, route=["inn", "inn"])
        )
        self.state.update(awareness_protocol=1, conversation_active=0)
        self.app.patrol_tick("mira", self.state)
        self.app.patrol_runtime["mira"]["next"] = 0

    def test_completion_and_game_timeout_advance(self):
        self.prepare()
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(self.app.redis.last()["patrol"], 1)
        job = self.app.action_jobs["mira"]
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(self.app.patrol_runtime["mira"]["index"], 0)
        job["status"] = "completed"
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(self.app.patrol_runtime["mira"]["index"], 1)
        self.app.patrol_runtime["mira"]["next"] = 0
        self.app.action_last["mira"] = 0
        self.app.patrol_tick("mira", self.state)
        self.app.action_jobs["mira"]["status"] = "timed out"
        self.app.patrol_tick("mira", self.state)
        self.assertFalse(self.app.patrol_runtime["mira"].get("halted"))
        self.assertEqual(self.app.patrol_runtime["mira"]["index"], 0)

    def test_conversation_combat_and_old_bridge_do_not_dispatch(self):
        for changes in (
            {"conversation_active": 1},
            {"combat": 1},
            {"mode": "dm"},
            {"awareness_protocol": 0},
        ):
            self.prepare()
            before = len(self.app.redis.commands)
            self.app.patrol_tick("mira", dict(self.state, **changes))
            self.assertEqual(before, len(self.app.redis.commands))

    def test_stop_stays_stopped_and_configuration_roundtrips(self):
        self.prepare()
        saved = actions.settings(self.app.action_config)
        self.assertTrue(saved["npcs"]["mira"]["patrol"]["enabled"])
        self.app.stop_action("mira")
        before = len(self.app.redis.commands)
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(before, len(self.app.redis.commands))
        with self.assertRaises(ValueError):
            self.app.save_action_policy(
                "mira", dict(actions.DEFAULT_POLICY, enabled=True)
            )

    def test_missing_ack_halts_without_resending(self):
        self.prepare()
        self.app.patrol_tick("mira", self.state)
        self.app.action_jobs["mira"]["started"] = time.monotonic() - 46
        before = len(self.app.redis.commands)
        self.app.patrol_tick("mira", self.state)
        self.assertTrue(self.app.patrol_runtime["mira"]["halted"])
        self.assertEqual(before, len(self.app.redis.commands))

    def test_linked_stop_uses_live_contact_position(self):
        self.prepare()
        self.state.update(area="inn", x=0, y=0, z=0)
        self.app.states["contact"] = dict(self.state, x=19, y=12)
        duty = self.app.action_config["npcs"]["mira"]["patrol"]
        duty["checkins"] = {"inn": "contact"}
        self.app.patrol_tick("mira", self.state)
        destination = self.app.redis.last()["destination"]
        self.assertAlmostEqual(((destination["x"]-19)**2 + (destination["y"]-12)**2)**0.5, 2.0)
        self.assertEqual(self.app.action_config["destinations"]["inn"]["x"], 1)

    def test_missing_contact_does_not_walk_to_old_marker(self):
        self.prepare()
        self.app.action_config["npcs"]["mira"]["patrol"]["checkins"] = {"inn": "missing"}
        before = len(self.app.redis.commands)
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(len(self.app.redis.commands), before)
        self.assertFalse(self.app.patrol_runtime["mira"].get("halted"))

    def test_moving_contact_is_reapproached_before_checkin(self):
        self.prepare()
        self.state.update(area="inn", x=0, y=0, z=0)
        self.app.states["contact"] = dict(self.state, x=19, y=12)
        self.app.action_config["npcs"]["mira"]["patrol"]["checkins"] = {"inn": "contact"}
        self.app.patrol_tick("mira", self.state)
        self.app.action_jobs["mira"]["status"] = "completed"
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(self.app.patrol_runtime["mira"]["index"], 0)
        self.assertEqual(self.app.patrol_runtime["mira"]["reapproaches"], 1)

    def test_live_bridge_area_name_and_missing_height(self):
        self.prepare()
        self.state.update(area="The Inn", area_resref="inn", area_tag="inn", x=0, y=0)
        self.app.states["contact"] = dict(self.state, x=19, y=12)
        self.app.action_config["npcs"]["mira"]["patrol"]["checkins"] = {"inn": "contact"}
        self.app.patrol_tick("mira", self.state)
        dest = self.app.redis.last()["destination"]
        self.assertEqual(dest["area"], "inn")
        self.assertEqual(dest["z"], self.point["z"])
        self.assertLess(dest["x"], 19.0)

    def test_unavailable_contact_advances_route(self):
        self.prepare()
        self.app.action_config["npcs"]["mira"]["patrol"]["checkins"] = {"inn": "missing"}
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(self.app.patrol_runtime["mira"]["index"], 1)

    def test_confirmed_timeout_does_not_retry_blocked_contact(self):
        self.prepare()
        self.state.update(area="inn", x=0, y=0, z=0)
        self.app.states["contact"] = dict(self.state, x=19, y=12)
        self.app.action_config["npcs"]["mira"]["patrol"]["checkins"] = {"inn": "contact"}
        self.app.patrol_tick("mira", self.state)
        self.app.action_jobs["mira"]["status"] = "timed out"
        self.app.patrol_tick("mira", self.state)
        self.assertEqual(self.app.patrol_runtime["mira"]["index"], 1)
        self.assertFalse(self.app.patrol_runtime["mira"].get("reapproaches"))
