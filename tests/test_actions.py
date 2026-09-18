import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from roleweaver import actions, backup
from roleweaver.service import Service
from roleweaver.store import DEFAULT_NPC


class FakeRedis:
    def __init__(self):
        self.commands = []

    def call(self, *args):
        self.commands.append(args)
        return 1

    def last(self):
        return json.loads(
            next(c[-1] for c in reversed(self.commands) if c[0] in ("LPUSH", "RPUSH"))
        )


class ActionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Service(
            Path(self.tmp.name), dict(provider="offline", world_id="test")
        )
        self.app.redis = FakeRedis()
        self.app.store.save(dict(DEFAULT_NPC, id="mira", name="Mira", mode="auto"))
        self.app.conversation_hello = dict(
            seen=time.monotonic(), session="game", actions_protocol=6
        )
        self.state = dict(
            session="game",
            epoch=1,
            tick=100,
            mode="auto",
            object="npc",
            seen=time.monotonic(),
        )
        self.app.states["mira"] = self.state
        self.point = dict(
            id="inn",
            name="Inn door",
            world="test",
            area="inn",
            area_tag="inn",
            x=1.0,
            y=2.0,
            z=0.0,
            facing=0.0,
        )

    def tearDown(self):
        self.app.pool.shutdown()
        self.app.store.db.close()
        self.tmp.cleanup()

    def enable(self):
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY, enabled=True, gestures=["bow"], destinations=[]
            ),
        )

    def test_disabled_by_default_and_strict_allowlist(self):
        self.assertEqual(self.app.action_choices("mira"), [])
        with self.assertRaises(ValueError):
            self.app.run_action("mira", "gesture:bow")
        for p in (
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                gestures=["attack"],
                destinations=[],
            ),
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                gestures=[],
                destinations=["unknown"],
            ),
            dict(actions.DEFAULT_POLICY, enabled=1, gestures=[], destinations=[]),
        ):
            with self.assertRaises(ValueError):
                self.app.save_action_policy("mira", p)

    def test_capture_requires_live_dm_matching_session_world(self):
        with self.assertRaises(ValueError):
            self.app.capture_destination("inn", "Inn", "dm")
        self.app.dms["dm"] = dict(
            seen=time.monotonic(), session="game", tick=100, token="private", name="DM"
        )
        self.app.capture_destination("inn", "Inn", "dm")
        c = self.app.redis.last()
        e = dict(
            self.point,
            kind="action_capture",
            request=c["request"],
            session="wrong",
            ok=1,
        )
        self.app.event(e)
        self.assertFalse(self.app.action_config["destinations"])
        e["session"] = "game"
        self.app.event(e)
        self.assertIn("inn", self.app.action_config["destinations"])
        with self.assertRaises(ValueError):
            self.app.capture_destination("inn", "Moved", "dm")

    def test_model_choices_cannot_supply_code_or_unapproved_targets(self):
        allowed = [dict(id="gesture:bow")]
        self.assertEqual(
            actions.parse_reply(
                '{"speech":"Greetings.","action":"gesture:bow"}', allowed
            ),
            ("Greetings.", "gesture:bow"),
        )
        for raw in (
            '{"speech":"Hi","action":"attack:player"}',
            '{"speech":"Hi","action":{},"script":"kill"}',
            "plain speech",
        ):
            with self.assertRaises(ValueError):
                actions.parse_reply(raw, allowed)

    def test_dispatch_and_cooldown_and_game_state(self):
        self.enable()
        self.app.run_action("mira", "gesture:bow")
        cmd = self.app.redis.last()
        self.assertEqual(cmd["kind"], "controlled_action")
        self.assertEqual(cmd["epoch"], 1)
        with self.assertRaises(ValueError):
            self.app.run_action("mira", "gesture:bow")
        self.app.event(dict(kind="ack", request=cmd["request"], ok=1))
        self.assertEqual(self.app.action_jobs["mira"]["status"], "running")
        self.app.action_state(
            "mira",
            dict(
                session="game", action_request=cmd["request"], action_status="completed"
            ),
        )
        self.assertEqual(self.app.action_jobs["mira"]["status"], "completed")
        self.assertFalse(self.app.action_choices("mira"))

    def test_revoke_stops_job_and_invalidates_pending_dialogue(self):
        self.enable()
        self.app.run_action("mira", "gesture:bow")
        old = self.app.generations["mira"]
        self.app.save_action_policy(
            "mira",
            dict(actions.DEFAULT_POLICY, enabled=False, destinations=[], gestures=[]),
        )
        self.assertEqual(self.app.redis.last()["kind"], "controlled_stop")
        self.assertGreater(self.app.generations["mira"], old)
        self.assertFalse(self.app.action_choices("mira"))

    def test_modes_staleness_and_combat_prevent_actions(self):
        self.enable()
        for changes in (
            dict(mode="paused"),
            dict(possessed=True),
            dict(dead=True),
            dict(combat=True),
            dict(seen=0),
        ):
            self.app.states["mira"] = dict(self.state, **changes)
            self.assertEqual(self.app.action_choices("mira"), [])

    def test_backup_contains_locations_and_permissions_and_legacy_clears_them(self):
        self.app.action_config["destinations"]["inn"] = self.point
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY, enabled=True, destinations=["inn"], gestures=[]
            ),
        )
        data = self.app.backup_data()
        self.assertEqual(data["version"], 11)
        checked = backup.validate(data)
        self.assertEqual(checked["controlled_actions"], self.app.action_config)
        with self.assertRaises(ValueError):
            self.app.delete_destination("inn")
        data["version"] = 6
        data.pop("controlled_actions")
        backup.replace(self.app.store, backup.validate(data))
        self.app.init_actions()
        self.assertFalse(self.app.action_config["destinations"])

    def test_action_waits_for_delivered_speech_and_rechecks_generation(self):
        self.enable()
        self.app.config["provider"] = "openai-compatible"
        profile = self.app.store.get("mira")
        gen = self.app.generations["mira"]
        with patch(
            "roleweaver.provider.reply",
            return_value='{"speech":"I greet you.","action":"gesture:bow"}',
        ):
            self.app.generate(
                "mira",
                "player",
                profile,
                gen,
                dict(self.state),
                "listener",
                speech="Hello",
            )
        speech = self.app.redis.last()
        self.assertEqual(speech["kind"], "say")
        self.assertFalse(self.app.action_jobs)
        self.app.event(dict(kind="ack", request=speech["request"], ok=1))
        self.assertEqual(self.app.redis.last()["kind"], "controlled_action")

    def test_blocked_output_never_dispatches_action(self):
        self.enable()
        self.app.config["provider"] = "openai-compatible"
        with patch(
            "roleweaver.provider.reply",
            return_value='{"speech":"As an AI language model I can help.","action":"gesture:bow"}',
        ):
            self.app.generate(
                "mira",
                "player",
                self.app.store.get("mira"),
                self.app.generations["mira"],
                dict(self.state),
                "listener",
                speech="Hello",
            )
        speech = self.app.redis.last()
        self.assertEqual(speech["kind"], "say")
        self.assertFalse(speech["action_choice"])
        self.app.event(dict(kind="ack", request=speech["request"], ok=1))
        self.assertFalse(self.app.action_jobs)

    def test_reconnect_adopts_running_action_without_replaying(self):
        self.app.action_state(
            "mira",
            dict(session="game", action_request="a" * 24, action_status="running"),
        )
        self.assertEqual(self.app.action_jobs["mira"]["status"], "running")
        self.assertFalse(self.app.redis.commands)


class MerchantAndLeadTests(unittest.TestCase):
    setUp = ActionsTests.setUp
    tearDown = ActionsTests.tearDown
    enable = ActionsTests.enable

    def test_old_permissions_do_not_enable_new_capabilities(self):
        migrated = actions.settings(
            dict(
                destinations={},
                npcs={"mira": dict(enabled=True, destinations=[], gestures=["bow"])},
            )
        )
        p = migrated["npcs"]["mira"]
        self.assertFalse(p["shop"])
        self.assertEqual(p["home"], "")
        self.assertEqual(p["lead_destinations"], [])

    def test_home_and_lead_only_use_saved_destinations(self):
        self.app.action_config["destinations"]["inn"] = self.point
        self.app.save_action_policy(
            "mira",
            dict(
                actions.DEFAULT_POLICY,
                enabled=True,
                lead_destinations=["inn"],
                home="inn",
            ),
        )
        ids = {a["id"] for a in self.app.action_choices("mira")}
        self.assertEqual(ids, {"home:inn", "lead:inn"})
        with self.assertRaises(ValueError):
            self.app.run_action("mira", "lead:inn")
        with self.assertRaises(ValueError):
            self.app.delete_destination("inn")
        self.app.run_action("mira", "home:inn")
        self.assertEqual(self.app.redis.last()["destination"], self.point)

    def test_merchant_requires_fresh_matching_stock(self):
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=True)
        )
        self.assertFalse(self.app.shop_context("mira")["available"])
        self.assertFalse(self.app.action_choices("mira"))
        event = dict(
            kind="merchant_stock",
            npc="mira",
            world="test",
            session="wrong",
            status="ready",
            rules_revision="defaults-v2",
            stock_revision="stock1",
            items=[dict(name="Dagger", quantity=1, price=2)],
        )
        self.app.merchant_event(event)
        self.assertFalse(self.app.shop_context("mira")["available"])
        event["session"] = "game"
        self.app.merchant_event(event)
        self.assertTrue(self.app.shop_context("mira")["available"])
        self.assertEqual(self.app.action_choices("mira")[0]["id"], "shop:open")
        self.app.shop_states["mira"]["seen"] = 0
        self.assertFalse(self.app.shop_context("mira")["available"])

    def test_shop_requires_requesting_player_and_preserves_native_price(self):
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=True)
        )
        self.app.merchant_event(
            dict(
                npc="mira",
                world="test",
                session="game",
                status="ready",
                rules_revision="defaults-v2",
                stock_revision="stock1",
                items=[],
            )
        )
        with self.assertRaises(ValueError):
            self.app.run_action("mira", "shop:open")
        self.app.run_action("mira", "shop:open", "player-object")
        cmd = self.app.redis.last()
        self.assertEqual(cmd["listener"], "player-object")
        self.assertNotIn("price", cmd)

    def test_shop_sync_and_disable_are_scoped_game_commands(self):
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=True)
        )
        self.app.sync_merchant("mira", dict(merchant_enabled=0))
        cmd = self.app.redis.last()
        self.assertEqual(cmd["kind"], "merchant_setup")
        self.assertEqual(cmd["world"], "test")
        self.assertEqual(cmd["enabled"], 1)
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=False)
        )
        self.app.shop_sent.clear()
        self.app.sync_merchant("mira", dict(merchant_enabled=1))
        self.assertEqual(self.app.redis.last()["enabled"], 0)

    def test_example_is_separate_paused_profile_with_shop_permission(self):
        result = self.app.merchant_example()
        p = self.app.store.get(result["npc"])
        self.assertEqual(p["mode"], "paused")
        self.assertTrue(self.app.action_config["npcs"][p["id"]]["shop"])
        with self.assertRaises(ValueError):
            self.app.merchant_example()

    def test_waiting_leader_remains_busy_and_stoppable(self):
        self.enable()
        self.app.action_state(
            "mira",
            dict(
                session="game",
                action_request="c" * 24,
                action_status="waiting for player",
            ),
        )
        self.assertEqual(self.app.action_jobs["mira"]["status"], "waiting for player")
        self.assertFalse(self.app.action_choices("mira"))
        self.app.stop_action("mira")
        self.assertEqual(self.app.redis.last()["kind"], "controlled_stop")

    def test_shop_context_is_in_provider_and_lore_grounding(self):
        from roleweaver import safeguards

        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=True)
        )
        self.app.merchant_event(
            dict(
                npc="mira",
                world="test",
                session="game",
                status="ready",
                rules_revision="defaults-v2",
                stock_revision="stock1",
                items=[dict(name="Dagger", quantity=1, price=2)],
            )
        )
        self.app.config["provider"] = "openai-compatible"
        with patch(
            "roleweaver.provider.reply",
            return_value='{"speech":"A dagger costs two gold.","action":""}',
        ) as reply:
            self.app.generate(
                "mira",
                "player",
                self.app.store.get("mira"),
                self.app.generations["mira"],
                dict(self.state),
                "listener",
                speech="What is for sale?",
            )
        profile = reply.call_args.args[1]
        self.assertEqual(profile["merchant"]["items"][0]["price"], 2)
        self.assertEqual(
            safeguards.trusted_sources(profile, [])["live_shop"]["items"][0]["price"], 2
        )

    def test_haggle_is_allowlisted_needs_customer_and_never_sends_prices(self):
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=True)
        )
        self.app.merchant_event(
            dict(
                npc="mira",
                world="test",
                session="game",
                status="ready",
                rules_revision="defaults-v2",
                stock_revision="stock1",
                items=[],
            )
        )
        self.assertIn("shop:haggle", {a["id"] for a in self.app.action_choices("mira")})
        with self.assertRaises(ValueError):
            self.app.run_action("mira", "shop:haggle")
        self.app.run_action("mira", "shop:haggle", "customer")
        cmd = self.app.redis.last()
        self.assertEqual(cmd["target"], "haggle")
        self.assertEqual(cmd["listener"], "customer")
        for key in ("price", "discount", "roll", "modifier"):
            self.assertNotIn(key, cmd)

    def test_personal_quote_scoped_to_customer_world_and_session(self):
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=True)
        )
        self.app.merchant_event(
            dict(
                npc="mira",
                world="test",
                session="game",
                status="ready",
                rules_revision="defaults-v2",
                stock_revision="stock1",
                items=[dict(name="Sword", price=33)],
            )
        )
        self.app.config["provider"] = "openai-compatible"
        quote = dict(
            price_stamp="test-stamp",
            npc="mira",
            world="test",
            session="game",
            listener="customer",
            status="ready",
            rules_revision="defaults-v2",
            stock_revision="stock1",
            items=[dict(name="Sword", price=30)],
            haggle=dict(discount=10),
        )
        for changes, expected in (
            ({}, 30),
            ({"listener": "someone_else"}, 33),
            ({"world": "elsewhere"}, 33),
            ({"session": "old"}, 33),
            ({"rules_revision": "old"}, 33),
            ({"stock_revision": "old"}, 33),
            ({"price_stamp": ""}, 33),
        ):
            with patch(
                "roleweaver.provider.reply",
                return_value='{"speech":"Let me check.","action":""}',
            ) as reply:
                self.app.generate(
                    "mira",
                    "player",
                    self.app.store.get("mira"),
                    self.app.generations["mira"],
                    dict(self.state),
                    "customer",
                    speech="Price?",
                    merchant_quote=dict(quote, **changes),
                )
            self.assertEqual(
                reply.call_args.args[1]["merchant"]["items"][0]["price"], expected
            )
            command = self.app.redis.last()
            if not changes:
                self.assertIn("Sword: 30 gold", command["text"])
                self.assertEqual(command["price_stamp"], "test-stamp")
            else:
                self.assertNotIn("33", command["text"])
                self.assertEqual(command["price_stamp"], "")

    def test_old_bridge_cannot_advertise_haggling(self):
        self.app.conversation_hello["actions_protocol"] = 2
        self.assertFalse(self.app.action_status()["ready"])


if __name__ == "__main__":
    unittest.main()
