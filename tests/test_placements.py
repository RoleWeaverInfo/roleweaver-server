import json
import tempfile
import unittest
from pathlib import Path

from roleweaver.service import Service
from roleweaver.store import Store


class RedisRecorder:
    def __init__(self):
        self.calls = []

    def call(self, *args):
        self.calls.append(args)


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Service(
            Path(self.tmp.name),
            {"provider": "offline", "placement_owner": "roleweaver"},
        )
        self.app.redis = RedisRecorder()
        self.placement = dict(
            npc="mira",
            world="world-a",
            session="old",
            area="inn",
            area_tag="inn",
            tag="rw_mira",
            resref="innkeeper",
            name="Mira",
            source="spawn",
            x=2.5,
            y=4.5,
            z=0.0,
            facing=90.0,
            dead=0,
        )
        self.app.store.save_placement(self.placement)

    def tearDown(self):
        self.app.pool.shutdown(wait=True)
        self.app.store.db.close()
        self.tmp.cleanup()

    def hello(self, session="new", world="world-a"):
        self.app.event(
            dict(kind="hello", world=world, session=session, tick=20, owns_placements=1)
        )

    def commands(self):
        return [json.loads(c[2]) for c in self.app.redis.calls if c[0] == "RPUSH"]

    def test_saved_location_survives_database_reopen(self):
        other = Store(Path(self.tmp.name) / "roleweaver.sqlite3")
        self.assertEqual(other.placements()[0]["x"], 2.5)
        other.db.close()

    def test_new_session_restores_once_with_original_coordinates(self):
        self.hello()
        self.hello()
        commands = self.commands()
        self.assertEqual(len(commands), 1)
        self.assertEqual(
            (commands[0]["session"], commands[0]["x"], commands[0]["kind"]),
            ("new", 2.5, "restore"),
        )

    def test_app_restart_in_same_game_does_not_respawn(self):
        self.hello(session="old")
        self.assertEqual(self.commands(), [])

    def test_other_world_is_not_restored(self):
        self.hello(world="world-b")
        self.assertEqual(self.commands(), [])

    def test_world_managed_service_never_requests_restore(self):
        self.app.config["placement_owner"] = "world"
        self.hello()
        self.assertEqual(self.commands(), [])

    def test_game_must_also_allow_restoration(self):
        self.app.event(
            dict(
                kind="hello", world="world-a", session="new", tick=20, owns_placements=0
            )
        )
        self.assertEqual(self.commands(), [])

    def test_dead_creature_is_not_automatically_resurrected(self):
        self.app.store.save_placement(dict(self.placement, dead=1))
        self.hello()
        self.assertEqual(self.commands(), [])

    def test_confirmed_placement_stops_restore_retries(self):
        self.hello()
        self.app.event(dict(self.placement, kind="placement", session="new"))
        self.app.restore_attempts.clear()
        self.hello()
        self.assertEqual(len(self.commands()), 1)

    def test_invalid_coordinates_do_not_replace_saved_location(self):
        with self.assertRaises(ValueError):
            self.app.store.save_placement(dict(self.placement, x=float("nan")))
        self.assertEqual(self.app.store.placements()[0]["x"], 2.5)
