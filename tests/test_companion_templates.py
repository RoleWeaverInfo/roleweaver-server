"""Starting templates must never replace a familiar's established identity."""

import copy
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from roleweaver import backup, companion_admin, companion_templates as templates
from roleweaver.companions import make_profile, profile_id
from roleweaver.service import Service
from tests import test_companions, test_recovery_http


class TemplateSelectionTests(unittest.TestCase):
    def test_standard_game_types_not_player_supplied_names(self):
        bank = templates.defaults()
        expected = (
            "bat",
            "cat",
            "hellhound",
            "imp",
            "fire_mephit",
            "ice_mephit",
            "pixie",
            "raven",
            "fairy_dragon",
            "pseudodragon",
            "eyeball",
        )
        for number, key in enumerate(expected):
            event = dict(
                creature=f"familiar:{number}",
                species="custom_resref",
                name="Bat cat imp",
                text="I am a raven",
            )
            self.assertEqual(templates.select(event, bank), key)
            p = make_profile("cp_" + "0" * 21, event, bank)
            self.assertEqual(p["personality"], bank[key]["profile"]["personality"])
            self.assertEqual(p["name"], event["name"])
        self.assertEqual(
            templates.select(dict(creature="familiar:255", name="Bat"), bank), "default"
        )

    def test_old_bridge_and_exact_pw_overrides(self):
        bank = templates.defaults()
        self.assertEqual(templates.select(dict(creature="nw_fm_cat"), bank), "cat")
        self.assertEqual(templates.select(dict(species="nw_fm_bat20"), bank), "bat")
        self.assertEqual(
            templates.select(dict(species="complicated_cat"), bank), "default"
        )
        bank["pixie"]["blueprints"] = ["custom_resref"]
        bank = templates.settings(bank)
        self.assertEqual(
            templates.select(
                dict(creature="familiar:1", species="CUSTOM_RESREF"), bank
            ),
            "pixie",
        )
        bank["default"]["blueprints"] = ["my_unknown"]
        self.assertEqual(
            templates.select(dict(creature="familiar:1", species="my_unknown"), bank),
            "default",
        )

    def test_templates_are_independent_copies_and_grant_no_permissions(self):
        bank = templates.defaults()
        bank["cat"]["profile"]["personality"] = "Edited"
        self.assertNotEqual(templates.defaults()["cat"], bank["cat"])
        event = dict(creature="familiar:1")
        profile = make_profile("cp_" + "0" * 21, event, bank)
        profile["personality"] = "Individual"
        self.assertEqual(bank["cat"]["profile"]["personality"], "Edited")
        self.assertEqual(set(bank["cat"]["profile"]), set(companion_admin.FIELDS))

    def test_bad_fields_and_ambiguous_blueprints_rejected(self):
        original = templates.defaults()
        for change in (
            {"blueprints": ["UPPER"]},
            {"blueprints": ["../outside"]},
            {"blueprints": ["x" * 17]},
            {"blueprints": ["same", "same"]},
            {"blueprints": [None]},
            {"blueprints": [f"b{i}" for i in range(33)]},
            {"profile": dict(original["cat"]["profile"], id="owner")},
            {"profile": dict(original["cat"]["profile"], lore="x" * 6001)},
            {"profile": dict(original["cat"]["profile"], voice=None)},
            {"enabled": True},
        ):
            with self.subTest(change=list(change)):
                bank = copy.deepcopy(original)
                bank["cat"].update(change)
                with self.assertRaises(ValueError):
                    templates.settings(bank)
        bank = copy.deepcopy(original)
        bank["cat"]["blueprints"] = bank["bat"]["blueprints"] = ["same"]
        with self.assertRaises(ValueError):
            templates.settings(bank)
        for bad in ([], {"unknown": {}}, {"cat": None}):
            with self.assertRaises(ValueError):
                templates.settings(bad)


class TemplateServiceTests(unittest.TestCase):
    setUp = test_companions.CompanionTests.setUp
    tearDown = test_companions.CompanionTests.tearDown
    run_chat = test_companions.CompanionTests.run_chat
    event = test_companions.CompanionTests.event

    def edit(self, key="cat", **changes):
        row = next(
            r
            for r in self.app.companion_template_dashboard()["templates"]
            if r["id"] == key
        )
        return dict(
            id=key,
            revision=row["revision"],
            profile=dict(row["profile"], **changes),
            blueprints=row["blueprints"],
        )

    def test_edit_applies_only_to_new_identity_without_extra_provider_call(self):
        npc = self.run_chat()
        old = self.app.store.get(npc)
        self.app.store.add_memory(npc, npc, "A saved friendship")
        before = self.app.store.transcript(npc)
        with patch("roleweaver.companions.provider.reply") as provider:
            self.app.save_companion_template(
                self.edit(personality="Patient book-loving cat")
            )
            self.assertFalse(provider.called)
        self.assertEqual(self.app.store.get(npc), old)
        self.assertEqual(self.app.store.transcript(npc), before)
        self.app.store.db.execute("DELETE FROM seen")
        self.run_chat(self.event(sequence=2, token="resummoned"))
        self.assertEqual(self.app.store.get(npc)["personality"], old["personality"])
        self.assertEqual(
            self.app.store.memories(npc, npc)[0]["text"], "A saved friendship"
        )
        self.run_chat(
            self.event(
                owner="second:Other wizard", object="456", token="other", sequence=3
            )
        )
        other = profile_id(self.app.salt, "test", "second:Other wizard", "nw_fm_cat")
        self.assertEqual(
            self.app.store.get(other)["personality"], "Patient book-loving cat"
        )

    def test_save_persists_restart_and_stale_save_has_no_side_effects(self):
        stale = self.edit(personality="Stale")
        self.app.save_companion_template(self.edit(personality="Fresh"))
        with self.assertRaisesRegex(ValueError, "changed elsewhere"):
            self.app.save_companion_template(stale)
        other = Service(Path(self.tmp.name), dict(provider="offline", world_id="test"))
        try:
            self.assertEqual(
                other.companion_templates["cat"]["profile"]["personality"], "Fresh"
            )
        finally:
            other.pool.shutdown()
            other.store.db.close()

    def test_explicit_copy_into_existing_profile_preserves_history_and_preferences(
        self,
    ):
        npc = self.run_chat()
        self.app.store.add_memory(npc, npc, "I know my owner")
        self.app.save_companion_template(self.edit(personality="New template"))
        old = self.app.store.get(npc)
        before = self.app.store.transcript(npc)
        self.app.save_companion_profile(
            dict(
                npc=npc,
                revision=companion_admin.revision(old),
                profile=self.app.companion_templates["cat"]["profile"],
            )
        )
        result = self.app.store.get(npc)
        self.assertEqual(result["personality"], "New template")
        for key in set(old) - set(templates.FIELDS):
            self.assertEqual(result[key], old[key])
        self.assertEqual(self.app.store.transcript(npc), before)
        self.assertEqual(
            self.app.store.memories(npc, npc)[0]["text"], "I know my owner"
        )

    def test_invalid_request_and_duplicate_mapping_do_not_write(self):
        for body in (
            None,
            [],
            dict(self.edit(), id=[]),
            dict(self.edit(), id="missing"),
            dict(self.edit(), extra=1),
        ):
            with self.assertRaises(ValueError):
                self.app.save_companion_template(body)
        self.assertIsNone(self.app.setting("companion_templates", None))
        self.app.save_companion_template(dict(self.edit(), blueprints=["test_cat"]))
        before = copy.deepcopy(self.app.companion_templates)
        with self.assertRaises(ValueError):
            self.app.save_companion_template(
                dict(self.edit("bat"), blueprints=["test_cat"])
            )
        self.assertEqual(self.app.companion_templates, before)

    def test_backup_roundtrip_legacy_and_malformed_restore(self):
        self.app.save_companion_template(
            dict(self.edit(lore="A library companion"), blueprints=["my_cat"])
        )
        data = self.app.backup_data()
        self.assertEqual(data["version"], 16)
        self.app.save_companion_template(self.edit(lore="Changed"))
        self.app.states.clear()
        self.app.restore_data(data)
        self.assertEqual(self.app.companion_templates, data["companion_templates"])
        for value in (None, [], {"cat": {}}, {"unrecognized": {}}):
            bad = dict(data, companion_templates=value)
            with self.assertRaises(ValueError):
                self.app.restore_data(bad)
            self.assertEqual(self.app.companion_templates, data["companion_templates"])
        missing = dict(data)
        del missing["companion_templates"]
        with self.assertRaisesRegex(ValueError, "Missing companion templates"):
            backup.validate(missing)
        missing["version"] = 14
        self.app.restore_data(missing)
        self.assertEqual(self.app.companion_templates, templates.defaults())


class TemplateHTTPTests(unittest.TestCase):
    setUp = test_recovery_http.RecoveryHTTPTests.setUp
    tearDown = test_recovery_http.RecoveryHTTPTests.tearDown
    start = test_recovery_http.RecoveryHTTPTests.start
    halt = test_recovery_http.RecoveryHTTPTests.halt
    request = test_recovery_http.RecoveryHTTPTests.request

    def test_authenticated_template_routes_and_conflict(self):
        self.start(authenticate=False)
        for path, body in (
            ("/api/companion-templates", None),
            ("/api/companion-template", {}),
        ):
            with self.assertRaises(HTTPError) as error:
                self.request(path, body)
            self.assertEqual(error.exception.code, 401)
        self.request("/api/login", {"password": "roleweaver"})
        data = self.request("/api/companion-templates")
        self.assertEqual(len(data["templates"]), 12)
        self.assertIn(
            b"Familiar starting templates", self.request("/companion-templates.js")
        )
        row = data["templates"][0]
        body = dict(
            id=row["id"],
            revision=row["revision"],
            profile=dict(row["profile"], lore="A custom background"),
            blueprints=["my_pet"],
        )
        with self.assertRaises(HTTPError) as error:
            self.request(
                "/api/companion-template", body, origin="https://outside.invalid"
            )
        self.assertEqual(error.exception.code, 403)
        result = self.request("/api/companion-template", body)
        self.assertEqual(
            result["templates"][0]["profile"]["lore"], "A custom background"
        )
        with self.assertRaises(HTTPError) as error:
            self.request("/api/companion-template", body)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.request("/api/companions")["companions"], [])
