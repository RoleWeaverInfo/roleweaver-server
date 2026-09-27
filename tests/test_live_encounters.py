"""Live scenes: preview immutability, separate ownership, restart and cleanup."""

import copy
import json
import time
import unittest
from unittest.mock import patch

from tests import test_actions
from roleweaver.encounters import DEFAULT_REACTION


class LiveEncounterTests(unittest.TestCase):
    tearDown = test_actions.ActionsTests.tearDown

    def setUp(self):
        test_actions.ActionsTests.setUp(self)
        self.app.config["allow_dm_spawn"] = True
        self.hello = dict(world="test", session="game", tick=100, live_protocol=1)
        self.app.tick_live(self.hello)
        self.app.dms["dm"] = dict(
            name="DM",
            token="dm-secret",
            seen=time.monotonic(),
            session="game",
            tick=100,
            live_protocol=1,
            area_object="area-object",
            area="inn",
            area_tag="inn",
            area_name="Inn",
            x=1.0,
            y=2.0,
            z=0.0,
            facing=0.0,
        )
        capture = self.app.capture_live("dm")["capture"]
        self.draft = dict(
            dm="dm",
            name="A meeting",
            profile="mira",
            count=2,
            blueprint="rw_custom",
            spawn=capture,
            trigger=capture,
            public_facts="The road is blocked.",
            goal="Ask for help.",
            boundaries="Allow refusal.",
            reaction=dict(DEFAULT_REACTION, enabled=True),
            repeat=False,
        )

    def place(self):
        preview = self.app.preview_live(self.draft)
        self.app.place_live(preview["preview"], "dm")
        return next(iter(self.app.live_scenes.values()))

    def confirm(self, scene):
        for request, p in list(self.app.pending.items()):
            if p["kind"] == "live_spawn":
                self.app.event(dict(kind="ack", request=request, ok=1))
        for n in scene["actors"]:
            self.app.states[n] = dict(self.state, live_owner=scene["owner"])

    def test_capture_requires_new_bridge_and_fresh_dm(self):
        self.app.dms["dm"]["live_protocol"] = 0
        with self.assertRaises(ValueError):
            self.app.capture_live("dm")
        self.app.dms["dm"]["live_protocol"] = 1
        self.app.dms["dm"]["seen"] -= 10
        with self.assertRaises(ValueError):
            self.app.capture_live("dm")

    def test_preview_has_no_world_changes_and_freezes_profile(self):
        before = len(self.app.store.list_npcs())
        preview = self.app.preview_live(self.draft)
        self.assertEqual(len(self.app.store.list_npcs()), before)
        self.assertEqual(self.app.redis.commands, [])
        p = self.app.store.get("mira")
        p["name"] = "Changed"
        self.app.store.save(p)
        self.app.place_live(preview["preview"], "dm")
        scene = next(iter(self.app.live_scenes.values()))
        self.assertEqual(
            [r["name"] for r in scene["actors"].values()], ["Mira 1", "Mira 2"]
        )
        with self.assertRaises(ValueError):
            self.app.place_live(preview["preview"], "dm")

    def test_reject_invalid_count_blueprint_repeat_and_distant_trigger(self):
        for key, value in [
            ("count", True),
            ("count", 9),
            ("blueprint", "../bad"),
            ("repeat", 1),
        ]:
            with self.assertRaises(ValueError):
                self.app.preview_live(dict(self.draft, **{key: value}))
        self.app.dms["dm"]["x"] = 50.0
        point = self.app.capture_live("dm")["capture"]
        with self.assertRaises(ValueError):
            self.app.preview_live(dict(self.draft, trigger=point))

    def test_captures_and_previews_expire_across_sessions(self):
        preview = self.app.preview_live(self.draft)
        self.app.live_previews[preview["preview"]]["time"] -= 121
        with self.assertRaises(ValueError):
            self.app.place_live(preview["preview"], "dm")
        self.app.dms["dm"]["session"] = "new"
        with self.assertRaises(ValueError):
            self.app.preview_live(self.draft)

    def test_live_and_persistent_are_separate_and_start_needs_confirmed_ownership(self):
        scene = self.place()
        key = scene["run"]["template"]["id"]
        self.assertEqual(self.app.encounter_status()["templates"], {})
        self.assertEqual(scene["run"]["status"], "placing")
        self.assertIsNone(self.app.encounter_for("mira"))
        with self.assertRaises(ValueError):
            self.app.control_live(key, "start")
        self.confirm(scene)
        self.assertEqual(scene["run"]["status"], "staged")
        n = next(iter(scene["actors"]))
        self.app.states[n]["live_owner"] = "wrong"
        with self.assertRaises(ValueError):
            self.app.control_live(key, "start")
        self.app.states[n]["live_owner"] = scene["owner"]
        self.app.control_live(key, "start")
        self.assertEqual(
            self.app.encounter_context(n)["public_facts"], "The road is blocked."
        )
        self.app.tick_live(self.hello)
        command = self.app.redis.last()
        self.assertEqual(command["kind"], "encounter_arm")
        self.assertEqual(command["live_owner"], scene["owner"])
        self.assertFalse(command["repeat"])
        self.assertEqual(command["anchor"]["area_object"], "area-object")

    def test_cleanup_scopes_commands_and_waits_for_all_acks(self):
        scene = self.place()
        self.confirm(scene)
        key = scene["run"]["template"]["id"]
        self.app.control_live(key, "cleanup")
        pending = [
            (r, p) for r, p in self.app.pending.items() if p["kind"] == "live_cleanup"
        ]
        self.assertEqual(len(pending), 2)
        self.assertEqual(self.app.redis.last()["owner"], scene["owner"])
        self.app.event(dict(kind="ack", request=pending[0][0], ok=1))
        self.assertEqual(scene["run"]["status"], "cleaning")
        self.app.event(dict(kind="ack", request=pending[1][0], ok=0))
        self.assertEqual(scene["run"]["status"], "cleaning")
        self.app.control_live(key, "cleanup")
        retry = [r for r, p in self.app.pending.items() if p["kind"] == "live_cleanup"]
        self.assertEqual(len(retry), 1)
        self.app.event(dict(kind="ack", request=retry[0], ok=1))
        self.assertEqual(scene["run"]["status"], "cleaned")
        self.assertEqual(self.app.store.get("mira")["name"], "Mira")
        self.assertEqual(len(self.app.store.list_npcs()), 3)

    def test_restart_pauses_journal_and_module_restart_expires_without_respawn(self):
        scene = self.place()
        self.confirm(scene)
        key = scene["run"]["template"]["id"]
        self.app.control_live(key, "start")
        self.app.init_live_encounters()
        self.assertEqual(self.app.live_scenes[key]["run"]["status"], "paused")
        self.app.redis.commands.clear()
        self.app.tick_live(dict(self.hello, session="new-game"))
        self.assertEqual(self.app.live_scenes[key]["run"]["status"], "expired")
        self.assertEqual(self.app.redis.commands, [])

    def test_lost_spawn_confirmation_requires_cleanup_not_automatic_retry(self):
        scene = self.place()
        self.app.pending.clear()
        self.app.redis.commands.clear()
        self.app.tick_live(self.hello)
        self.assertEqual(scene["run"]["status"], "staged")
        self.assertTrue(
            all(
                "confirmation missing" in r["placement"]
                for r in scene["actors"].values()
            )
        )
        self.assertEqual(self.app.redis.commands, [])

    def test_event_validation_and_combat_monitor_ownership(self):
        scene = self.place()
        self.confirm(scene)
        key = scene["run"]["template"]["id"]
        self.app.control_live(key, "start")
        npc = next(iter(scene["actors"]))
        event = dict(
            encounter=key,
            world="test",
            session="game",
            token=str(scene["run"]["started"]),
            npc=npc,
            status="warning",
        )
        before = len(scene["run"]["events"])
        self.app.live_game_event(dict(event, token="stale"))
        self.app.live_game_event(dict(event, npc="mira"))
        self.assertEqual(len(scene["run"]["events"]), before)
        self.app.live_game_event(event)
        self.assertIn(
            "Warning delivered", self.app.encounter_context(npc)["game_observation"]
        )
        self.app.redis.commands.clear()
        self.app.reconcile_encounter_combat(
            npc, dict(combat_encounter=key, combat_token=event["token"], session="game")
        )
        self.assertEqual(self.app.redis.commands, [])

    def test_restore_requires_live_cleanup(self):
        self.place()
        with self.assertRaisesRegex(ValueError, "Clean up live encounters"):
            self.app.restore_data(self.app.backup_data())

    def test_partial_submission_is_journalled(self):
        with patch.object(self.app, "live_send", side_effect=OSError("transport down")):
            scene = self.place()
        self.assertEqual(scene["run"]["status"], "staged")
        self.assertIn(
            "submission failed", next(iter(scene["actors"].values()))["placement"]
        )
        self.app.init_live_encounters()
        self.assertEqual(len(self.app.live_scenes), 1)

    def test_partial_start_disables_trigger_and_pause_retries_all_actors(self):
        scene = self.place()
        self.confirm(scene)
        key = scene["run"]["template"]["id"]
        with patch.object(
            self.app, "control", side_effect=["sent", OSError("connection lost")]
        ):
            with self.assertRaisesRegex(ValueError, "trigger remains disabled"):
                self.app.control_live(key, "start")
        self.assertEqual(scene["run"]["status"], "paused")
        with patch.object(
            self.app, "control", side_effect=[ValueError("unavailable"), "sent"]
        ) as control:
            self.app.control_live(key, "pause")
            self.assertEqual(control.call_count, 2)
        self.assertIn("Retry pause", scene["run"]["events"][-1])


if __name__ == "__main__":
    unittest.main()
