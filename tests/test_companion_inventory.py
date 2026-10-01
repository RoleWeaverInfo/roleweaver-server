"""Cargo capabilities never authorize arbitrary commands or expose player bags."""

import json
import time
import unittest
from unittest.mock import patch

from roleweaver import companion_inventory as cargo
from roleweaver.companions import GUIDANCE, LEGACY_GUIDANCE
from tests import test_companions


class CargoContextTests(unittest.TestCase):
    def event(self):
        return dict(
            seen=time.monotonic(),
            companion_inventory_protocol=1,
            companion_inventory=dict(
                available=1,
                items=[
                    dict(
                        ref="i1",
                        name="Potion",
                        quantity=2,
                        stackable=1,
                        owner="private-owner",
                        uuid="secret-item-uuid",
                    )
                ],
                choices=[
                    dict(
                        id="cpinv:0",
                        description="Collect the potion",
                        target="secret-game-object",
                        verb="pickup",
                    )
                ],
                ground=[],
                containers=[],
                player_inventory=["Private sword"],
                status="Item collected into the satchel.",
            ),
        )

    def test_default_and_invalid_policy_fail_closed(self):
        self.assertEqual(cargo.policy()["containers"], [])
        for bad in (
            dict(radius=True),
            dict(radius=999),
            dict(max_value=-1),
            dict(enabled="yes"),
            dict(containers=[{}]),
            dict(unknown=True),
        ):
            with self.subTest(bad=bad):
                self.assertFalse(
                    cargo.configured(dict(companion_inventory=bad))["enabled"]
                )

    def test_only_public_rows_and_offered_ids_reach_model(self):
        view, choices = cargo.context(self.event(), {})
        self.assertTrue(view["available"])
        self.assertEqual(
            choices, [dict(id="cpinv:0", description="Collect the potion")]
        )
        self.assertEqual(view["items"][0]["quantity"], 2)
        rendered = json.dumps([view, choices])
        for private in (
            "private-owner",
            "secret-item-uuid",
            "secret-game-object",
            "Private sword",
        ):
            self.assertNotIn(private, rendered)

    def test_old_disabled_and_stale_snapshots_offer_nothing(self):
        for event, config in (
            (dict(self.event(), seen=0), {}),
            (dict(self.event(), companion_inventory_protocol=0), {}),
            (self.event(), dict(companion_inventory=dict(enabled=False))),
        ):
            self.assertEqual(cargo.context(event, config)[1], [])
            self.assertFalse(cargo.context(event, config)[0]["available"])

    def test_choice_ids_are_bounded_unique_and_not_script_names(self):
        event = self.event()
        event["companion_inventory"]["choices"] = [
            dict(id="cpinv:0", description="First"),
            dict(id="cpinv:0", description="Duplicate"),
            dict(id="cpinv:96", description="Out of range"),
            dict(id="attack:player", description="No"),
            dict(id="cpinv:1", description=""),
            None,
        ]
        self.assertEqual(
            cargo.context(event, {})[1], [dict(id="cpinv:0", description="First")]
        )


class CargoServiceTests(unittest.TestCase):
    setUp = test_companions.CompanionTests.setUp
    tearDown = test_companions.CompanionTests.tearDown
    event = test_companions.CompanionTests.event
    run_chat = test_companions.CompanionTests.run_chat

    def cargo_event(self):
        data = CargoContextTests().event()
        data.pop("seen")
        return self.event(**data)

    def test_service_dispatches_only_offered_inventory_action(self):
        def inspect(config, profile, memories, history):
            self.assertIn(
                "cpinv:0", [row["id"] for row in profile["controlled_actions"]]
            )
            self.assertEqual(profile["inventory"]["items"][0]["name"], "Potion")
            self.assertNotIn("Private sword", json.dumps([profile, memories, history]))
            return '{"speech":"I will collect it.","action":"cpinv:0"}'

        npc = self.run_chat(self.cargo_event(), effect=inspect)
        self.assertEqual(self.app.redis.last()["action"], "cpinv:0")
        self.assertNotIn("companion_inventory", self.app.store.get(npc))

    def test_unoffered_action_and_changed_binding_never_transfer(self):
        before = len(self.app.redis.commands)
        self.run_chat(
            self.cargo_event(), reply='{"speech":"All right.","action":"cpinv:1"}'
        )
        self.assertEqual(len(self.app.redis.commands), before)

    def test_disabling_inventory_removes_capabilities(self):
        self.app.config["companion_inventory"] = dict(enabled=False)
        before = len(self.app.redis.commands)
        self.run_chat(
            self.cargo_event(), reply='{"speech":"All right.","action":"cpinv:0"}'
        )
        self.assertEqual(len(self.app.redis.commands), before)

    def test_new_owner_turn_prevents_late_inventory_command(self):
        before = len(self.app.redis.commands)

        def interrupt(*args):
            self.app.event(
                self.event(kind="companion_state", sequence=2, token="new-turn")
            )
            return '{"speech":"I will collect it.","action":"cpinv:0"}'

        self.run_chat(self.cargo_event(), effect=interrupt)
        self.assertEqual(len(self.app.redis.commands), before)

    def test_guardrails_drop_inventory_action(self):
        before = len(self.app.redis.commands)
        with patch.object(self.app, "review_dialogue", return_value="block"):
            self.run_chat(
                self.cargo_event(), reply='{"speech":"All right.","action":"cpinv:0"}'
            )
        self.assertEqual(len(self.app.redis.commands), before)

    def test_only_legacy_default_guidance_is_migrated(self):
        npc = self.run_chat()
        profile = self.app.store.get(npc)
        profile["guidance"] = LEGACY_GUIDANCE
        self.app.store.save(profile)
        self.run_chat(self.event(token="next"))
        self.assertEqual(self.app.store.get(npc)["guidance"], GUIDANCE)
        profile["guidance"] = "Custom familiar instructions"
        self.app.store.save(profile)
        self.run_chat(self.event(token="third"))
        self.assertEqual(
            self.app.store.get(npc)["guidance"], "Custom familiar instructions"
        )
