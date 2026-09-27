"""Inventory permissions, finite choices and command dispatch safety."""

import time
import unittest
from unittest.mock import patch
from roleweaver import actions, inventory, nearby
from roleweaver.store import DEFAULT_NPC
from tests import test_actions


class InventoryTests(unittest.TestCase):
    setUp = test_actions.ActionsTests.setUp
    tearDown = test_actions.ActionsTests.tearDown

    def ready(self, **flags):
        self.app.conversation_hello["inventory_protocol"] = 1
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                inventory=dict(inventory.DEFAULT, **flags),
            ),
        )
        self.state.update(
            inventory_protocol=1,
            inventory_revision=self.app.inventory_revision("mira"),
            inventory=dict(
                items=[
                    dict(ref="i1", name="Dagger", quantity=1, healing=0, stackable=0),
                    dict(ref="i2", name="Potion", quantity=2, healing=1, stackable=1),
                ],
                containers=[
                    dict(
                        ref="v1",
                        name="Chest",
                        items=[
                            dict(ref="i3", name="Sword", quantity=1, stackable=0),
                            dict(ref="i4", name="Arrows", quantity=20, stackable=1),
                        ],
                    )
                ],
            ),
            nearby_targets=nearby.targets(
                [
                    dict(
                        ref="v1",
                        kind="container",
                        label="Chest",
                        tag="supply",
                        distance=3,
                    ),
                    dict(
                        ref="v2",
                        kind="character",
                        label="Guard",
                        peer="guard",
                        distance=4,
                    ),
                ]
            ),
        )

    def ids(self, listener="player"):
        return {a["id"] for a in self.app.action_choices("mira", listener)}

    def test_default_and_validation(self):
        self.ready()
        self.assertEqual(self.ids(), set())
        self.assertEqual(
            actions.policy(actions.DEFAULT_POLICY, {})["inventory"], inventory.DEFAULT
        )
        for changes in (
            {"take": 1},
            {"radius": 41},
            {"radius": True},
            {"max_value": -1},
            {"barter_percent": 0},
            {"containers": ["x", "x"]},
        ):
            with self.assertRaises(ValueError):
                inventory.policy(dict(inventory.DEFAULT, **changes))

    def test_container_allowlist_and_inspection(self):
        self.ready(take=True, deposit=True, fetch=True, give=True)
        self.assertNotIn("take:v1:i3", self.ids())
        self.ready(
            containers=["supply"], take=True, deposit=True, fetch=True, give=True
        )
        self.assertIn("inspect:v1", self.ids())
        self.assertIn("fetch:v1:i3:player", self.ids())
        self.assertNotIn("fetch:v1:i4:player", self.ids())
        self.state["inventory"]["containers"] = []
        self.assertNotIn("take:v1:i3", self.ids())
        self.assertIn("deposit:v1:i1", self.ids())
        self.state["nearby_targets"]["v1"]["distance"] = 41
        self.assertNotIn("inspect:v1", self.ids())

    def test_freshness_revision_and_encounter(self):
        self.ready(give=True)
        self.assertIn("give:player:i1", self.ids())
        old = dict(self.state)
        for overrides in (
            {"inventory_protocol": 0},
            {"inventory_revision": "old"},
            {"seen": time.monotonic() - 5},
            {"combat": 1},
        ):
            self.state.update(overrides)
            self.assertEqual(self.ids(), set())
            self.state.update(old)
        with patch.object(self.app, "encounter_for", return_value="reserved"):
            self.assertEqual(self.ids(), set())

    def test_peer_requires_own_permission(self):
        self.ready(give=True, exchange=True, receive=True)
        self.assertNotIn("give:v2:i1", self.ids())
        self.app.store.save(dict(DEFAULT_NPC, id="guard", name="Guard", mode="auto"))
        self.app.save_action_policy(
            "guard",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                inventory=dict(inventory.DEFAULT, receive=True, exchange=True),
            ),
        )
        self.app.states["guard"] = dict(
            self.state, inventory_revision=self.app.inventory_revision("guard")
        )
        self.assertIn("give:v2:i1", self.ids())
        self.assertIn("swap:v2:i1:i1", self.ids())
        self.app.states["guard"]["combat"] = 1
        self.assertNotIn("give:v2:i1", self.ids())

    def test_dispatch_uses_only_existing_tokens(self):
        self.ready(containers=["supply"], take=True, give=True, fetch=True)
        for bad in ("give:player:madeup", "take:v9:i3", "fetch:v1:i4:player"):
            with self.assertRaises(ValueError):
                self.app.run_action("mira", bad, "player")
        self.app.run_action("mira", "fetch:v1:i3:player", "player")
        c = self.app.redis.last()
        self.assertEqual(
            (c["container"], c["item"], c["recipient"]), ("v1", "i3", "player")
        )
        self.assertEqual(c["inventory_revision"], self.app.inventory_revision("mira"))
        self.assertNotIn("blueprint", c)

    def test_player_consent_and_privacy(self):
        self.ready(receive=True)
        self.assertEqual(self.ids(), {"exchange:player"})
        self.assertEqual(self.ids(""), set())
        self.app.run_action("mira", "exchange:player", "player")
        self.assertEqual(self.app.redis.last()["action"], "exchange")
        self.state["inventory"]["player_items"] = [{"name": "Private item"}]
        self.assertNotIn("Private item", str(inventory.snapshot(self.state)))
        self.state["inventory"]["containers"] = None
        self.assertEqual(inventory.snapshot(self.state)["containers"], [])

    def test_sync_revokes_and_waits_for_game_acknowledgement(self):
        self.ready(give=True)
        self.app.save_action_policy("mira", dict(actions.DEFAULT_POLICY))
        self.app.sync_inventory("mira", self.state)
        self.assertEqual(self.app.redis.last()["enabled"], 0)
        self.assertEqual(self.ids(), set())

    def test_assistance_needs_real_potion(self):
        self.ready(heal=True)
        self.assertIn("aid:player:i2", self.ids())
        self.assertIn("aid:self:i2", self.ids())
        self.assertNotIn("aid:player:i1", self.ids())
        self.state["inventory"]["items"] = []
        self.assertEqual(self.ids(), set())

    def test_inventory_short_cooldown_does_not_inherit_walk_delay(self):
        self.ready(give=True)
        self.app.action_last["mira"] = time.monotonic()
        self.assertIn("give:player:i1", self.ids())
        self.app.inventory_last["mira"] = time.monotonic()
        self.assertNotIn("give:player:i1", self.ids())
        self.app.inventory_last["mira"] = time.monotonic() - 3
        self.assertIn("give:player:i1", self.ids())

    def test_healing_kit_is_an_actual_assistance_choice(self):
        self.ready(heal=True)
        self.state["inventory"]["items"] = [
            dict(
                ref="i3",
                name="Bandages",
                quantity=1,
                healing=1,
                healing_kind="bandage",
                stackable=1,
            )
        ]
        self.assertIn("aid:player:i3", self.ids())
        self.assertIn("aid:self:i3", self.ids())

    def test_equipment_and_item_use(self):
        self.ready(
            equip=True,
            use_items=True,
            usable_resrefs=["nw_it_mpotion001"],
            give=True,
            deposit=True,
            containers=["supply"],
        )
        self.state["inventory"]["items"][0].update(
            slots=[4], uses=[dict(index=0, name="Power")]
        )
        self.assertIn("equip:self:i1:4", self.ids())
        self.assertIn("use:self:i1:0", self.ids())
        self.state["inventory"]["items"][0]["equipped"] = 1
        self.assertIn("unequip:self:i1", self.ids())
        self.assertNotIn("equip:self:i1:4", self.ids())
        self.assertNotIn("give:player:i1", self.ids())
        self.assertNotIn("deposit:v1:i1", self.ids())

    def test_old_inventory_policy_migrates_disabled(self):
        old = {
            k: v
            for k, v in inventory.DEFAULT.items()
            if k not in ("equip", "use_items", "usable_resrefs")
        }
        p = inventory.policy(old)
        self.assertFalse(p["equip"])
        self.assertFalse(p["use_items"])
        self.assertEqual(p["usable_resrefs"], [])

    def test_equipment_command_dispatch(self):
        self.ready(equip=True)
        self.state["inventory"]["items"][0]["slots"] = [4]
        self.app.run_action("mira", "equip:self:i1:4", "player")
        command = self.app.redis.last()
        self.assertEqual(command["item"], "i1")
        self.assertEqual(command["recipient"], "self")
        self.assertEqual(command["slot"], 4)
        self.assertEqual(
            command["inventory_revision"], self.app.inventory_revision("mira")
        )
