"""Payment receipts and opt-in combat authority, independent of model prose."""

import unittest
from unittest.mock import patch
from roleweaver import actions, interactions, director, nearby, perception
from roleweaver.store import DEFAULT_NPC
from tests import test_actions


class InteractionTests(unittest.TestCase):
    setUp = test_actions.ActionsTests.setUp
    tearDown = test_actions.ActionsTests.tearDown

    def ready(self):
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                payment=dict(interactions.payment_policy(), enabled=True),
            ),
        )
        self.state.update(
            interaction_protocol=1,
            interaction_revision=self.app.interaction_revision("mira"),
        )

    def test_payment_requires_permission_listener_and_fresh_revision(self):
        self.assertEqual(self.app.payment_choices("mira", "player"), [])
        self.ready()
        self.assertEqual(len(self.app.payment_choices("mira", "player")), 5)
        self.assertEqual(self.app.payment_choices("mira", ""), [])
        self.state["interaction_revision"] = "old"
        self.assertEqual(self.app.payment_choices("mira", "player"), [])

    def test_offer_is_not_receipt_and_confirmed_receipt_is_idempotent(self):
        self.ready()
        self.app.run_interaction("mira", "payment:100", "player")
        self.assertEqual(self.app.payment_receipts, [])
        offer, record = next(iter(self.app.payment_offers.items()))
        event = dict(
            record, offer=offer, world="test", payer="synthetic-key:Test", status="paid"
        )
        for change in [
            dict(amount=99),
            dict(epoch=99),
            dict(session="old"),
            dict(listener="other"),
            dict(status="requested"),
        ]:
            self.app.payment_event(dict(event, **change))
            self.assertEqual(self.app.payment_receipts, [])
        self.app.payment_event(event)
        self.app.payment_event(event)
        self.assertEqual(len(self.app.payment_receipts), 1)
        self.assertEqual(self.app.payment_context("mira")[0]["amount"], 100)
        self.assertNotIn("payer", self.app.payment_receipts[0])

    def test_exchange_payment_request_opens_offer_without_receipt(self):
        self.ready()
        event = dict(
            kind="payment_request",
            npc="mira",
            world="test",
            session=self.state["session"],
            epoch=self.state["epoch"],
            listener="pc",
        )
        self.app.event(dict(event, epoch=999))
        self.assertEqual(self.app.payment_offers, {})
        self.app.event(event)
        self.assertEqual(len(self.app.payment_offers), 1)
        self.assertEqual(self.app.payment_receipts, [])
        self.assertEqual(self.app.action_jobs["mira"]["choice"], "payment:100")

    def test_completed_payment_does_not_interrupt_later_game_states(self):
        self.ready()
        self.app.run_interaction("mira", "payment:100", "player")
        offer, record = next(iter(self.app.payment_offers.items()))
        self.app.payment_event(
            dict(
                record,
                offer=offer,
                world="test",
                payer="synthetic-key:Test",
                status="paid",
            )
        )
        receipt_job = dict(self.app.action_jobs["mira"])
        # Ordinary states raised KeyError after payment, backing up the bridge.
        # Anonymous running states must not replace the receipt either.
        for fields in (
            {},
            dict(action_request="", action_status=""),
            dict(action_request="", action_status="running"),
            dict(action_request="old-movement", action_status="completed"),
        ):
            with self.subTest(fields=fields):
                with patch.object(self.app, "sync_merchant") as sync:
                    self.app.event(dict(self.state, kind="state", npc="mira", **fields))
                    sync.assert_called_once()
                self.assertEqual(self.app.action_jobs["mira"], receipt_job)
        self.app.action_state(
            "mira",
            dict(
                session="game", action_request="new-movement", action_status="running"
            ),
        )
        self.assertEqual(self.app.action_jobs["mira"]["request"], "new-movement")
        self.assertEqual(len(self.app.payment_receipts), 1)

    def test_invalid_limits_and_targets(self):
        for changes in [dict(minimum=101), dict(amount=True), dict(minimum=0)]:
            with self.assertRaises(ValueError):
                interactions.payment_policy(
                    dict(interactions.payment_policy(), **changes)
                )
        with self.assertRaises(ValueError):
            interactions.combat_policy(dict(interactions.combat_policy(), targets=[{}]))
        with self.assertRaises(ValueError):
            interactions.combat_policy(dict(interactions.combat_policy(), enabled=True))

    def test_both_npcs_must_opt_in_and_target_must_be_visible(self):
        self.ready()
        self.app.store.save(dict(DEFAULT_NPC, id="guard", name="Guard", mode="auto"))
        self.app.save_action_policy(
            "guard",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                npc_combat=dict(interactions.combat_policy(), allow_targeted=True),
            ),
        )
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                npc_combat=dict(
                    interactions.combat_policy(),
                    enabled=True,
                    targets=["guard"],
                    conditions="Only if attacked",
                ),
            ),
        )
        self.state["interaction_revision"] = self.app.interaction_revision("mira")
        self.app.states["guard"] = dict(
            self.state, interaction_revision=self.app.interaction_revision("guard")
        )
        rows = [
            dict(ref="v1", kind="character", label="Guard", distance=3, peer="guard")
        ]
        self.state.update(
            perception_protocol=2,
            perception_tick=100,
            surroundings=perception.observations(rows),
            nearby_targets=nearby.targets(rows),
        )
        self.assertEqual(
            self.app.npc_combat_choices("mira")[0]["id"], "attack_npc:guard"
        )
        self.app.action_config["npcs"]["guard"]["npc_combat"]["allow_targeted"] = False
        self.assertEqual(self.app.npc_combat_choices("mira"), [])

    def test_director_cannot_invent_attacks_or_mix_attack_and_resolve(self):
        value = dict(
            summary="Threat",
            phase="fighting",
            reason="Approved",
            goals={},
            operation="continue",
            actions={"mira": "attack_npc:guard"},
        )
        with self.assertRaises(ValueError):
            director.validate(value, ["mira"])
        choices = {"mira": [dict(id="attack_npc:guard")]}
        self.assertEqual(
            director.validate(value, ["mira"], action_choices=choices)["actions"],
            value["actions"],
        )
        with self.assertRaises(ValueError):
            director.validate(
                dict(value, operation="resolve"), ["mira"], action_choices=choices
            )
