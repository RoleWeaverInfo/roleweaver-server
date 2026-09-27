"""Dynamic targets cannot bypass permissions, freshness or social interruption."""

import time
import unittest
from unittest.mock import patch
from roleweaver import actions, nearby, perception
from roleweaver.store import DEFAULT_NPC
from tests import test_actions


class NearbyTests(unittest.TestCase):
    setUp = test_actions.ActionsTests.setUp
    tearDown = test_actions.ActionsTests.tearDown

    def ready(self, **permissions):
        rows = [
            dict(
                ref="v1",
                kind="door",
                label="Gate",
                distance=4,
                usable=True,
                open="closed",
            ),
            dict(
                ref="v2", kind="placeable", label="Chair", distance=3, tag="chair_one"
            ),
            dict(ref="v3", kind="character", label="Guard", distance=5, peer="guard"),
            dict(
                ref="v4",
                kind="character",
                label="Secret player name",
                distance=2,
                player=True,
            ),
            dict(
                ref="v5", kind="container", label="Chest", distance=2, tag="chair_one"
            ),
        ]
        self.state.update(
            nearby_protocol=1,
            perception_protocol=2,
            perception_tick=100,
            surroundings=perception.observations(rows),
            nearby_targets=nearby.targets(rows),
        )
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                nearby=dict(nearby.DEFAULT, **permissions),
            ),
        )
        return rows

    def ids(self):
        return {a["id"] for a in self.app.action_choices("mira")}

    def test_default_migration_does_not_grant_new_permissions(self):
        saved = actions.settings(
            dict(
                destinations={},
                npcs={"mira": dict(actions.DEFAULT_POLICY, enabled=True)},
            )
        )
        self.assertEqual(saved["npcs"]["mira"]["nearby"], nearby.DEFAULT)
        self.ready()
        self.assertEqual(self.ids(), set())
        for bad in (
            dict(nearby.DEFAULT, radius=13),
            dict(nearby.DEFAULT, radius=True),
            dict(nearby.DEFAULT, doors=1),
            dict(nearby.DEFAULT, seat_tags=["x", "x"]),
        ):
            with self.assertRaises(ValueError):
                nearby.policy(bad)

    def test_only_permitted_visible_targets_are_selectable(self):
        self.ready(doors=True, seat_tags=["chair_one"])
        self.assertEqual(self.ids(), {"open_door:v1", "sit:v2"})
        for action in ("approach:v1", "sit:v5", "open_door:deadbeef", "visit:v3"):
            with self.assertRaises(ValueError):
                self.app.run_action("mira", action)
        self.app.run_action("mira", "sit:v2")
        command = self.app.redis.last()
        self.assertEqual(command["seat_tag"], "chair_one")
        self.assertEqual(command["target"], "v2")
        self.assertEqual(command["radius"], 8)
        self.assertNotIn("destination", command)

    def test_old_bridge_stale_scan_radius_and_missing_target_reject(self):
        self.ready(approach=True, radius=3)
        self.assertEqual(self.ids(), {"approach:v2", "approach:v5"})
        for override in (
            dict(nearby_protocol=0),
            dict(perception_tick=90),
            dict(seen=time.monotonic() - 10),
        ):
            original = dict(self.state)
            self.state.update(override)
            self.assertEqual(self.ids(), set())
            self.state.update(original)
        self.state["nearby_targets"].pop("v2")
        with self.assertRaises(ValueError):
            self.app.run_action("mira", "approach:v2")

    def test_metadata_is_not_in_model_perception(self):
        rows = self.ready(approach=True)
        snapshot = perception.snapshot(self.state)
        for row in snapshot["objects"]:
            self.assertNotIn("ref", row)
            self.assertNotIn("tag", row)
            self.assertNotIn("peer", row)
        self.assertNotIn("Secret player name", str(snapshot))
        self.assertEqual(nearby.targets([dict(rows[0], ref="7fffffff")]), {})

    def peer(self):
        self.app.store.save(dict(DEFAULT_NPC, id="guard", name="Guard", mode="auto"))
        self.app.states["guard"] = dict(
            self.state, nearby_npcs=["mira"], checkins_protocol=1, conversation_active=0
        )
        self.state.update(
            nearby_npcs=["guard"], checkins_protocol=1, conversation_active=0
        )
        self.app.save_action_policy(
            "guard",
            dict(actions.DEFAULT_POLICY, nearby=dict(nearby.DEFAULT, receive=True)),
        )

    def test_visit_requires_opt_in_idle_peer_and_completion_before_talking(self):
        self.ready(talk=True)
        self.assertNotIn("visit:v3", self.ids())
        self.peer()
        self.assertIn("visit:v3", self.ids())
        self.app.states["guard"]["conversation_active"] = 1
        self.assertNotIn("visit:v3", self.ids())
        self.app.states["guard"]["conversation_active"] = 0
        self.app.run_action("mira", "visit:v3")
        with patch.object(self.app, "start_checkin") as start:
            self.app.visit_tick("mira")
            start.assert_not_called()
            self.app.action_jobs["mira"]["status"] = "completed"
            self.app.visit_tick("mira")
            self.app.visit_tick("mira")
            self.assertEqual(start.call_count, 1)

    def test_failed_or_revoked_visit_never_starts_conversation(self):
        for status, generation in (("timed out", 0), ("completed", 999)):
            self.ready(talk=True)
            self.peer()
            self.app.action_jobs["mira"] = dict(
                visit_peer="guard", visit_generation=generation, status=status
            )
            with patch.object(self.app, "start_checkin") as start:
                self.app.visit_tick("mira")
                start.assert_not_called()

    def test_cooldown_and_encounter_reservations(self):
        self.ready(talk=True, approach=True)
        self.peer()
        self.app.checkin_last["mira:guard"] = time.time()
        self.assertNotIn("visit:v3", self.ids())
        with patch.object(self.app, "encounter_for", return_value="reserved"):
            self.assertEqual(self.ids(), set())

    def test_social_requests_never_substitute_landmarks_or_approach(self):
        choices = [
            dict(id=x)
            for x in (
                "walk:patrol_kevin",
                "home:visitor_table",
                "approach:v1",
                "visit:v2",
                "gesture:bow",
            )
        ]
        for request in (
            "Go talk to the innkeeper",
            "Please speak with Tavern Owner",
            "Check in with the wizard",
            "Walk over and chat with her",
        ):
            result = nearby.dialogue_choices(choices, request)
            self.assertEqual([a["id"] for a in result], ["visit:v2", "gesture:bow"])
        self.assertEqual(
            nearby.dialogue_choices(choices, "Walk to the visitor table"), choices
        )
        self.assertEqual(
            nearby.dialogue_choices(choices, "Walk up to the innkeeper"), choices
        )
        self.assertEqual(
            nearby.dialogue_choices(
                [dict(id="walk:visitor_table")], "Go talk to the innkeeper"
            ),
            [],
        )

    def test_prompt_explains_unavailable_visit_even_without_any_actions(self):
        import json
        from roleweaver import provider

        with patch.object(
            provider, "complete", return_value="I cannot visit them right now."
        ) as complete:
            provider.reply(
                dict(
                    provider="openai-compatible",
                    base_url="https://example.invalid/v1",
                    model="test",
                ),
                dict(DEFAULT_NPC, social_visit_request=True),
                [],
                [],
            )
        system = json.loads(complete.call_args.args[1])["messages"][0]["content"]
        self.assertIn("CURRENT live position", system)
        self.assertIn("If no visit action", system)

    def test_area_wide_awareness_does_not_expand_movement_permission(self):
        self.ready(approach=True)
        distant = dict(
            ref="v99",
            kind="character",
            label="Distant guard",
            distance=80,
            peer="guard",
        )
        self.state.update(
            perception_protocol=3,
            surroundings=[distant],
            nearby_targets=nearby.targets([distant], area_wide=True),
        )
        self.assertEqual(len(perception.snapshot(self.state)["objects"]), 1)
        self.assertEqual(self.ids(), set())
