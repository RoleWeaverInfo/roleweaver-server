import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from roleweaver.service import Service
from roleweaver import backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Service(
            Path(self.temp.name), {"provider": "offline", "api_key": "DO NOT EXPORT"}
        )

    def tearDown(self):
        self.app.pool.shutdown(wait=True)
        self.app.store.db.close()
        self.temp.cleanup()

    def test_roundtrip_and_player_identity_survive_restart(self):
        self.app.store.message("mira", "player-hash", "player", "Hello")
        self.app.store.add_memory("mira", "player-hash", "A remembered fact")
        self.app.save_world_lore("World fact")
        data = self.app.backup_data()
        self.assertNotIn("DO NOT EXPORT", str(data))
        data["identity_salt"] = "a" * 64
        self.app.restore_data(data)
        self.assertEqual(self.app.store.transcript("mira")[0]["text"], "Hello")
        self.assertEqual(
            self.app.store.memories("mira")[0]["text"], "A remembered fact"
        )
        self.assertEqual(self.app.store.world_lore(), "World fact")
        self.assertEqual(self.app.store.get("mira")["mode"], "paused")
        other = Service(Path(self.temp.name), {"provider": "offline"})
        self.assertEqual(other.salt, "a" * 64)
        other.pool.shutdown()
        other.store.db.close()
        self.assertEqual(
            len(list(Path(self.temp.name).glob("before-restore-*.json"))), 1
        )

    def test_bad_backup_never_changes_data(self):
        data = self.app.backup_data()
        for change in (
            {"version": 99},
            {"identity_salt": "bad"},
            {"messages": [{"npc": "unknown"}]},
            {"world_lore": "x" * 20001},
        ):
            bad = dict(data, **change)
            with self.assertRaises(ValueError):
                self.app.restore_data(bad)
            self.assertEqual(self.app.store.get("mira")["name"], "Mira")

    def test_duplicate_ids_rejected(self):
        data = self.app.backup_data()
        data["npcs"] *= 2
        with self.assertRaises(ValueError):
            backup.validate(data)

    def test_restore_waits_for_game_pause(self):
        self.app.states["mira"] = {"mode": "auto", "seen": 0}
        with patch.object(
            self.app, "command", side_effect=ValueError("NPC is not connected")
        ):
            with self.assertRaises(ValueError):
                self.app.restore_data(self.app.backup_data())
        self.assertEqual(self.app.store.get("mira")["name"], "Mira")
        self.assertFalse(self.app.restoring)
        self.assertEqual(list(Path(self.temp.name).glob("before-restore-*")), [])

    def test_empty_backup_is_valid(self):
        data = self.app.backup_data()
        data["npcs"] = []
        self.app.restore_data(data)
        self.assertEqual(self.app.store.list_npcs(), [])

    def test_transaction_rolls_back_on_failure(self):
        data = backup.validate(self.app.backup_data())
        data["messages"] = [
            dict(npc="mira", player="x", text=None, created=0, speaker="player")
        ]
        with self.assertRaises(Exception):
            backup.replace(self.app.store, data)
        self.assertEqual(self.app.store.get("mira")["name"], "Mira")

    def test_saved_creature_roundtrip(self):
        placement = dict(
            npc="mira",
            world="world",
            session="old",
            area="starting_area",
            area_tag="starting_area",
            tag="rw_mira",
            resref="innkeeper",
            name="Mira",
            source="dm_persistent",
            x=1.5,
            y=2.5,
            z=0.0,
            facing=90.0,
            dead=0,
        )
        self.app.store.save_placement(placement)
        data = self.app.backup_data()
        self.assertEqual(data["version"], 11)
        self.app.store.db.execute("DELETE FROM placements")
        self.app.store.db.commit()
        self.app.restore_data(data)
        restored = self.app.store.placements()[0]
        for k, v in placement.items():
            self.assertEqual(restored[k], v)

    def test_old_backup_without_locations_still_loads(self):
        data = self.app.backup_data()
        data["version"] = 1
        data.pop("placements")
        self.assertEqual(backup.validate(data)["placements"], [])

    def test_bad_saved_location_rejected(self):
        data = self.app.backup_data()
        data["placements"] = [dict(npc="unknown")]
        with self.assertRaises(ValueError):
            self.app.restore_data(data)

    def test_running_world_cannot_overwrite_restored_location(self):
        self.app.placement_restore_hold = {"world": "old-session"}
        with patch.object(self.app.store, "save_placement") as save:
            self.app.event(dict(kind="placement", world="world", session="old-session"))
        save.assert_not_called()
