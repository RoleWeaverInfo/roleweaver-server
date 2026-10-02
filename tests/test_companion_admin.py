"""Dashboard permissions and character edits preserve owner state and history."""

import copy
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from roleweaver import backup, companion_admin as admin, companion_preferences
from roleweaver.service import Service
from tests import test_companions
from tests import test_recovery_http
from roleweaver.companions import make_profile
from urllib.error import HTTPError


class CompanionAdminTests(unittest.TestCase):
    setUp = test_companions.CompanionTests.setUp
    tearDown = test_companions.CompanionTests.tearDown
    run_chat = test_companions.CompanionTests.run_chat
    event = test_companions.CompanionTests.event

    def edit(self, npc, **fields):
        p = self.app.store.get(npc)
        return dict(
            npc=npc,
            revision=admin.revision(p),
            profile={k: fields.get(k, p[k]) for k in admin.FIELDS},
        )

    def hello(self, **changes):
        return dict(
            dict(
                world="test",
                session="game",
                tick=50,
                companion_protocol=1,
                companion_admin_protocol=1,
                companion_enabled=int(self.app.companions_enabled()),
                companion_generation=self.app.companion_generation,
            ),
            **changes,
        )

    def test_switch_persists_and_cannot_enable_player_opt_in(self):
        npc = self.run_chat()
        before = self.app.companion_generation
        self.app.companion_hello(self.hello())
        self.assertEqual(self.app.companion_dashboard()["status"], "applied")
        result = self.app.save_companion_enabled(dict(enabled=False))
        self.assertNotEqual(before, self.app.companion_generation)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["status"], "pending")
        self.assertFalse(self.app.companion_pending)
        self.app.companion_hello(self.hello(companion_enabled=1))
        self.assertEqual(self.app.redis.last()["enabled"], 0)
        self.app.companion_hello(self.hello())
        self.assertEqual(self.app.companion_dashboard()["status"], "applied")
        self.assertTrue(self.app.store.get(npc))
        self.app.config["companions_enabled"] = True
        self.assertFalse(
            self.app.companions_enabled()
        )  # Dashboard overrides install default.
        other = Service(
            Path(self.tmp.name),
            dict(provider="offline", world_id="test", companions_enabled=True),
        )
        try:
            self.assertFalse(other.companions_enabled())
        finally:
            other.pool.shutdown()
            other.store.db.close()
        self.app.save_companion_enabled(dict(enabled=True))
        with patch.object(self.app.pool, "submit") as submit:
            self.app.event(self.event(kind="companion_state", active=0, opted_in=0))
        self.assertFalse(submit.called)
        row = self.app.companion_dashboard()["companions"][0]
        self.assertEqual(row["status"], "Player AI off")

    def test_bad_switch_input_has_no_effect(self):
        for body in (
            None,
            dict(enabled=1),
            dict(enabled="false"),
            dict(enabled=False, owner="key"),
        ):
            with self.assertRaises(ValueError):
                self.app.save_companion_enabled(body)
        self.assertIsNone(self.app.setting("companion_admin", None))

    def test_public_owner_metadata_survives_disconnect_without_authentication_keys(
        self,
    ):
        npc = self.run_chat()
        row = self.app.companion_dashboard()["companions"][0]
        self.assertEqual(row["owner"], "Wizard")
        self.assertEqual(row["id"], npc)
        self.assertNotIn("key:Wizard", json.dumps(self.app.companion_dashboard()))
        self.assertNotIn("binding", json.dumps(self.app.companion_dashboard()))
        self.app.companion_states.clear()
        row = self.app.companion_dashboard()["companions"][0]
        self.assertEqual(row["owner"], "Wizard")
        self.assertFalse(row["connected"])
        self.assertEqual(len(self.app.companion_dashboard()["companions"]), 1)
        self.assertEqual(self.app.store.placements(), [])

    def test_edit_preserves_memories_preferences_identity_and_build(self):
        npc = self.run_chat()
        self.app.store.add_memory(npc, npc, "Saved history")
        preferences = {npc: dict(companion_preferences.DEFAULT, tone=2)}
        self.app.set_setting("companion_preferences", preferences)
        old = self.app.store.get(npc)
        history = self.app.store.transcript(npc)
        self.app.save_companion_profile(
            self.edit(
                npc, personality="Curious and kind", lore="Raised in the royal library."
            )
        )
        updated = self.app.store.get(npc)
        self.assertEqual(updated["personality"], "Curious and kind")
        self.assertEqual(updated["lore"], "Raised in the royal library.")
        for k in set(old) - {"personality", "lore"}:
            self.assertEqual(updated[k], old[k])
        self.assertEqual(self.app.store.transcript(npc), history)
        self.assertEqual(self.app.store.memories(npc, npc)[0]["text"], "Saved history")
        self.assertEqual(self.app.setting("companion_preferences", {}), preferences)

    def test_unknown_companion_world_npc_and_extra_profile_fields_are_rejected(self):
        npc = self.run_chat()
        good = self.edit(npc)
        for bad in (
            dict(good, npc="mira"),
            dict(good, npc="cp_" + "0" * 21),
            dict(good, profile=dict(good["profile"], id="other")),
            dict(good, profile=dict(good["profile"], lore="x" * 6001)),
            dict(good, profile=dict(good["profile"], personality=None)),
        ):
            with self.assertRaises(ValueError):
                self.app.save_companion_profile(bad)

    def test_concurrent_profile_edits_require_review(self):
        npc = self.run_chat()
        stale = self.edit(npc, lore="Old editor overwrite")
        self.app.save_companion_profile(
            self.edit(npc, lore="Another DM's saved background")
        )
        with self.assertRaisesRegex(ValueError, "changed elsewhere"):
            self.app.save_companion_profile(stale)
        self.assertEqual(
            self.app.store.get(npc)["lore"], "Another DM's saved background"
        )

    def test_late_provider_result_is_discarded_after_profile_edit_or_disable(self):
        for operation in ("edit", "disable"):
            self.app.store.db.execute("DELETE FROM seen")
            self.app.save_companion_enabled(dict(enabled=True))
            before = len(self.app.redis.commands)

            def delayed(config, profile, memories, history):
                if operation == "edit":
                    self.app.save_companion_profile(
                        self.edit(profile["id"], personality="New personality")
                    )
                else:
                    self.app.save_companion_enabled(dict(enabled=False))
                return '{"speech":"Obsolete reply","action":""}'

            self.run_chat(effect=delayed)
            self.assertEqual(len(self.app.redis.commands), before)

    def test_backup_roundtrip_legacy_and_validation(self):
        self.run_chat()
        self.app.save_companion_enabled(dict(enabled=False))
        data = self.app.backup_data()
        self.assertEqual(data["version"], 15)
        self.assertNotIn("key:Wizard", json.dumps(data["companion_admin"]))
        clean = backup.validate(data)
        self.app.save_companion_enabled(dict(enabled=True))
        self.app.states.clear()  # No live world-NPC pause handshake in this fixture.
        self.app.restore_data(data)
        self.assertEqual(self.app.companion_admin, clean["companion_admin"])
        old = dict(data, version=13)
        old.pop("companion_admin")
        self.assertEqual(backup.validate(old)["companion_admin"], admin.settings())
        missing = dict(data)
        missing.pop("companion_admin")
        with self.assertRaises(ValueError):
            backup.validate(missing)
        bad = copy.deepcopy(data)
        bad["companion_admin"]["enabled"] = "yes"
        with self.assertRaises(ValueError):
            backup.validate(bad)
        bad = copy.deepcopy(data)
        next(iter(bad["companion_admin"]["registry"].values()))["owner_key"] = "private"
        with self.assertRaises(ValueError):
            backup.validate(bad)

    def test_game_confirmation_is_not_inferred_from_service_save(self):
        self.assertEqual(self.app.companion_dashboard()["status"], "offline")
        h = self.hello()
        h.pop("companion_admin_protocol")
        self.app.companion_hello(h)
        self.assertEqual(self.app.companion_dashboard()["status"], "upgrade_required")
        self.app.companion_hello(self.hello(companion_generation="previous-generation"))
        self.assertEqual(self.app.companion_dashboard()["status"], "pending")
        self.app.companion_hello(self.hello())
        self.assertEqual(self.app.companion_dashboard()["status"], "applied")
        self.app.companion_admin_hello["seen"] = time.monotonic() - 20
        self.assertEqual(self.app.companion_dashboard()["status"], "offline")


class CompanionAdminHTTPTests(unittest.TestCase):
    setUp = test_recovery_http.RecoveryHTTPTests.setUp
    tearDown = test_recovery_http.RecoveryHTTPTests.tearDown
    start = test_recovery_http.RecoveryHTTPTests.start
    halt = test_recovery_http.RecoveryHTTPTests.halt
    request = test_recovery_http.RecoveryHTTPTests.request

    def test_routes_persist_switch_and_edit_only_existing_companions(self):
        app = Service(
            self.root / "data", dict(provider="offline", world_id="http_test")
        )
        npc = "cp_" + "1" * 21
        app.store.save(make_profile(npc, dict(name="Test familiar", species="cat")))
        app.pool.shutdown()
        app.store.db.close()
        self.start()
        self.assertIn(
            b"companion personalities".lower(), self.request("/companions.js").lower()
        )
        data = self.request("/api/companions")
        self.assertFalse(data["enabled"])
        row = data["companions"][0]
        body = dict(
            npc=npc,
            revision=row["revision"],
            profile=dict(row["profile"], lore="A remembered upbringing."),
        )
        changed = self.request("/api/companion-profile", body)
        self.assertEqual(
            changed["companions"][0]["profile"]["lore"], "A remembered upbringing."
        )
        with self.assertRaises(HTTPError) as exc:
            self.request("/api/companion-profile", body)
        self.assertEqual(exc.exception.code, 400)
        for route, body in [
            ("/api/companion-settings", dict(enabled=True)),
            ("/api/companion-profile", body),
        ]:
            with self.assertRaises(HTTPError) as exc:
                self.request(route, body, origin="https://outside.invalid")
            self.assertEqual(exc.exception.code, 403)
        self.request("/api/companion-settings", dict(enabled=True))
        self.halt()
        self.start()
        self.assertTrue(self.request("/api/companions")["enabled"])
