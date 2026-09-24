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

    def test_completion_advances_but_failure_halts(self):
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
        self.assertTrue(self.app.patrol_runtime["mira"]["halted"])

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
