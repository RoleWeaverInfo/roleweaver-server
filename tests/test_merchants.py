import unittest, time, json
from unittest.mock import patch
import test_actions as base_tests
from roleweaver import merchants, actions, backup


class MerchantTests(unittest.TestCase):
    setUp = base_tests.ActionsTests.setUp
    tearDown = base_tests.ActionsTests.tearDown

    def enable(self):
        self.app.save_action_policy(
            "mira", dict(actions.DEFAULT_POLICY, enabled=True, shop=True)
        )
        self.app.merchant_event(
            dict(
                npc="mira",
                world="test",
                session="game",
                status="ready",
                rules_revision=self.app.merchant_entry("mira")["revision"],
                stock_revision="stock1",
                items=[dict(item="object1", name="Dagger", quantity=2, price=8)],
            )
        )

    def test_rule_validation_and_caps(self):
        for changes in (
            {"chance": -1},
            {"chance": 101},
            {"discount": 11},
            {"discount": -1},
            {"cooldown": 0},
            {"enabled": 1},
            {"chance": True},
            {"cooldown": 86401},
        ):
            with self.assertRaises(ValueError):
                merchants.rules(dict(merchants.DEFAULT_RULES, **changes))

    def test_changed_rules_wait_for_game_and_invalidate_old_revision(self):
        self.enable()
        old = self.app.merchant_entry("mira")["revision"]
        self.app.save_merchant_rules(
            "mira", dict(merchants.DEFAULT_RULES, chance=25), old
        )
        new = self.app.merchant_entry("mira")["revision"]
        self.assertNotEqual(old, new)
        self.assertFalse(self.app.shop_context("mira")["available"])
        self.app.sync_merchant("mira", dict(merchant_enabled=1, merchant_revision=old))
        cmd = self.app.redis.last()
        self.assertEqual(cmd["rules"]["chance"], 25)
        self.assertEqual(cmd["rules_revision"], new)
        with self.assertRaises(ValueError):
            self.app.save_merchant_rules("mira", dict(merchants.DEFAULT_RULES), old)

    def test_disabled_haggling_keeps_shop_open(self):
        self.enable()
        self.app.save_merchant_rules(
            "mira", dict(merchants.DEFAULT_RULES, enabled=False), "defaults-v2"
        )
        self.enable()
        ids = {a["id"] for a in self.app.action_choices("mira")}
        self.assertIn("shop:open", ids)
        self.assertNotIn("shop:haggle", ids)

    def test_stock_add_validates_catalog_quantity_and_stale_inventory(self):
        self.enable()
        for kwargs in (
            {"item": "fake"},
            {"quantity": 0},
            {"quantity": True},
            {"quantity": 21},
            {"revision": "old"},
        ):
            args = dict(
                npc="mira",
                operation="add",
                revision="stock1",
                item="nw_wswdg001",
                quantity=1,
            )
            args.update(kwargs)
            with self.assertRaises(ValueError):
                self.app.edit_merchant_stock(**args)
        self.app.edit_merchant_stock("mira", "add", "stock1", "nw_wswdg001", 2)
        c = self.app.redis.last()
        self.assertEqual(c["quantity"], 2)
        self.assertEqual(c["kind"], "merchant_stock_edit")
        self.assertNotIn("price", c)
        with self.assertRaises(ValueError):
            self.app.edit_merchant_stock("mira", "add", "stock1", "nw_wswdg001", 2)

    def test_removal_requires_exact_current_row(self):
        self.enable()
        for item, qty in (("other", 2), ("object1", 1)):
            with self.assertRaises(ValueError):
                self.app.edit_merchant_stock("mira", "remove", "stock1", item, qty)
        self.app.edit_merchant_stock("mira", "remove", "stock1", "object1", 2)
        self.assertEqual(self.app.redis.last()["item"], "object1")

    def test_confirmation_matches_session_and_timeout_is_unknown(self):
        self.enable()
        self.app.edit_merchant_stock("mira", "add", "stock1", "nw_wswdg001", 1)
        c = self.app.redis.last()
        p = self.app.pending[c["request"]]
        self.app.merchant_ack(p, dict(request=c["request"], session="other", ok=1))
        self.assertEqual(self.app.merchant_jobs["mira"]["status"], "pending")
        self.app.merchant_jobs["mira"]["started"] = 0
        self.assertEqual(
            self.app.merchant_status()["merchants"][0]["job"]["status"], "unknown"
        )
        self.app.merchant_ack(p, dict(request=c["request"], session="game", ok=1))
        self.assertEqual(self.app.merchant_jobs["mira"]["status"], "confirmed")

    def test_backup_rules_and_restore_rotates_offers(self):
        self.enable()
        self.app.save_merchant_rules(
            "mira", dict(merchants.DEFAULT_RULES, chance=75), "defaults-v2"
        )
        data = self.app.backup_data()
        self.assertEqual(data["version"], 11)
        old = data["merchant_configs"]["mira"]["revision"]
        backup.replace(self.app.store, backup.validate(data))
        self.app.init_actions()
        self.assertEqual(self.app.merchant_entry("mira")["rules"]["chance"], 75)
        self.assertNotEqual(self.app.merchant_entry("mira")["revision"], old)

    def test_legacy_backup_gets_safe_default_rules(self):
        self.enable()
        data = self.app.backup_data()
        data["version"] = 9
        data.pop("merchant_configs")
        backup.replace(self.app.store, backup.validate(data))
        self.app.init_actions()
        self.assertEqual(
            self.app.merchant_entry("mira")["rules"], merchants.DEFAULT_RULES
        )

    def test_model_cannot_choose_admin_stock_commands(self):
        self.enable()
        with self.assertRaises(ValueError):
            actions.parse_reply(
                '{"speech":"A gift.","action":"merchant_stock_edit"}',
                self.app.action_choices("mira"),
            )

    def test_legacy_rules_migrate_once_and_invalidate_offers(self):
        old = dict(
            mira=dict(
                revision="a" * 24,
                rules=dict(
                    enabled=True,
                    dc=15,
                    strong_dc=20,
                    discount=5,
                    strong_discount=10,
                    cooldown=600,
                ),
            )
        )
        migrated = merchants.configs(old)
        self.assertEqual(
            migrated["mira"]["rules"],
            dict(enabled=True, chance=30, discount=5, cooldown=600),
        )
        self.assertNotEqual(migrated["mira"]["revision"], old["mira"]["revision"])
        self.assertEqual(merchants.configs(old), migrated)
        self.assertEqual(merchants.configs(migrated), migrated)

    def test_chance_endpoints_allowed(self):
        for chance in (0, 100):
            self.assertEqual(
                merchants.rules(dict(merchants.DEFAULT_RULES, chance=chance))["chance"],
                chance,
            )

    def test_price_reply_uses_final_quote_not_model_arithmetic(self):
        shop = dict(
            available=True,
            customer_quote=True,
            items=[
                dict(name="Longsword", price=27),
                dict(name="Short Sword", price=18),
            ],
        )
        for wrong in ("The sword costs 24 gold.", "Thirty gold.", "Twenty-four coins."):
            text, quoted = merchants.price_reply(
                wrong, "What is the price of the longsword?", shop
            )
            self.assertTrue(quoted)
            self.assertIn("Longsword: 27 gold", text)
            self.assertNotIn("24", text)
            self.assertNotIn("30", text)
        text, quoted = merchants.price_reply("Only 24 gold!", "Tell me about it", shop)
        self.assertTrue(quoted)
        self.assertIn("27 gold", text)
        self.assertEqual(
            merchants.price_reply(
                "I can offer 20 gold.", "Discount?", shop, "shop:haggle"
            ),
            ("Let me see what price I can offer you.", False),
        )

    def test_missing_personal_quote_does_not_fall_back_to_list_price(self):
        text, quoted = merchants.price_reply(
            "30 gold.",
            "Price?",
            dict(available=True, items=[dict(name="Sword", price=30)]),
        )
        self.assertFalse(quoted)
        self.assertNotIn("30", text)

    def test_catalogue_matches_game_allowlist(self):
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[1] / "bridge/rw_stock.nss"
        ).read_text()
        for item in merchants.CATALOG:
            self.assertIn('ref=="' + item["id"] + '"', source)


if __name__ == "__main__":
    unittest.main()
