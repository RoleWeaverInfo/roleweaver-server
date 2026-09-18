import tempfile, unittest
from pathlib import Path
from roleweaver.store import Store, DEFAULT_NPC
from roleweaver.authoring import catalog, creature_build, visible_lore, validate_lore
from roleweaver import backup


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.sqlite3")

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def test_templates_are_valid_and_independent(self):
        items = catalog()["templates"]
        self.assertEqual(len(items), 5)
        for t in items:
            p = self.store.save(dict(DEFAULT_NPC, **t))
            self.assertTrue(creature_build(p))
            self.assertEqual(p["mode"], "paused")
        self.assertGreater(len(catalog()["appearances"]), 800)

    def test_lore_audience_filter(self):
        rows = []
        for i, a, t in [
            ("one", "public", ""),
            ("two", "faction", "town_watch"),
            ("three", "npc", "mira"),
            ("four", "dm", ""),
            ("five", "npc", "orren"),
            ("six", "faction", "temple"),
        ]:
            rows.append(
                validate_lore(
                    dict(
                        id=i,
                        title=i,
                        text="secret-" + i,
                        audience=a,
                        target=t,
                        disclosure="Keep private",
                    )
                )
            )
        p = dict(DEFAULT_NPC, factions="town_watch")
        got = visible_lore(rows, p)
        self.assertEqual([e["title"] for e in got], ["one", "two", "three"])
        p["factions"] = ""
        self.assertEqual([e["title"] for e in visible_lore(rows, p)], ["one", "three"])
        self.assertNotIn("secret-four", str(got))

    def test_creature_and_lore_survive_backup_restore(self):
        p = dict(
            DEFAULT_NPC,
            appearance="6",
            race="6",
            gender="1",
            npc_class="2",
            level="17",
            factions="temple",
        )
        self.store.save(p)
        entry = dict(
            id="temple_secret",
            title="Temple secret",
            text="Hidden chamber",
            audience="faction",
            target="temple",
            disclosure="Do not disclose",
        )
        self.store.save_access_lore(entry)
        placement = dict(
            npc="mira",
            world="test",
            session="old",
            area="a",
            area_tag="a",
            tag="mira",
            resref="rw_base",
            name="Mira",
            source="dm_persistent",
            x=1,
            y=2,
            z=0,
            facing=0,
            dead=0,
            creature=creature_build(p),
        )
        self.store.save_placement(placement)
        data = backup.validate(backup.export(self.store, "a" * 64))
        backup.replace(self.store, data)
        self.assertEqual(self.store.get("mira")["level"], "17")
        self.assertEqual(self.store.access_lore(), [dict(entry, active=True)])
        self.assertEqual(self.store.placements()[0]["creature"], placement["creature"])

    def test_legacy_backup_defaults(self):
        data = backup.export(self.store, "a" * 64)
        data["version"] = 2
        data.pop("access_lore")
        for k in ("appearance", "race", "gender", "npc_class", "level", "factions"):
            data["npcs"][0].pop(k)
        clean = backup.validate(data)
        self.assertEqual(clean["npcs"][0]["level"], "1")
        self.assertEqual(clean["access_lore"], [])

    def test_reject_unsupported_builds(self):
        for k, v in [
            ("level", "0"),
            ("level", "41"),
            ("gender", "3"),
            ("appearance", "999999"),
            ("npc_class", "255"),
            ("race", "22"),
        ]:
            with self.assertRaises(ValueError):
                self.store.save(dict(DEFAULT_NPC, **{k: v}))
        with self.assertRaises(ValueError):
            self.store.save(dict(DEFAULT_NPC, factions="Town Watch"))

    def test_invalid_audience_and_target(self):
        with self.assertRaises(ValueError):
            validate_lore(
                dict(id="test", title="Title", text="Fact", audience="anyone")
            )
        with self.assertRaises(ValueError):
            self.store.save_access_lore(
                dict(
                    id="test",
                    title="Title",
                    text="Fact",
                    audience="npc",
                    target="missing",
                )
            )
