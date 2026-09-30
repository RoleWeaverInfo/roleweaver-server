"""Preservation and native-link invariants for the editable encounter areas."""

import copy
from pathlib import Path
import unittest

from tools.expand_demo_world import (
    expand,
    pack_module,
    HALL,
    FOREST,
    CAVE,
    ARE,
    GIT,
    GIC,
)
from tools.gff import read, write
from tools.module_copy import resources

ROOT = Path(__file__).resolve().parents[1]


class DemoExpansionTests(unittest.TestCase):
    def setUp(self):
        # The optional example is the same module in each distribution.
        path = ROOT / "demo/world/YourWorld_Fixed.mod"
        if not path.exists():
            path = ROOT / "addon/example-world/YourWorld_Fixed.mod"
        self.raw = path.read_bytes()
        self.old = {(n, k): b for n, k, b in resources(self.raw)}
        if (FOREST, ARE) in self.old:
            # Reconstruct the pre-expansion input for preservation tests without
            # keeping a duplicate module binary in source or distributions.
            self.old = {
                key: raw
                for key, raw in self.old.items()
                if key[0] not in (FOREST, CAVE)
            }
            mod = read(self.old["module", 2014])[1]
            mod[1]["Mod_Area_list"] = (
                15,
                [
                    n
                    for n in mod[1]["Mod_Area_list"][1]
                    if n[1]["Area_Name"][1] not in (FOREST.encode(), CAVE.encode())
                ],
            )
            self.old["module", 2014] = write(b"IFO V3.2", mod)
            are = read(self.old[HALL, ARE])[1]
            for i in (16, 18):
                are[1]["Tile_List"][1][i][1]["Tile_ID"] = (
                    are[1]["Tile_List"][1][i][1]["Tile_ID"][0],
                    149,
                )
            self.old[HALL, ARE] = write(b"ARE V3.2", are)
            for kind, signature in ((GIT, b"GIT V3.2"), (GIC, b"GIC V3.2")):
                obj = read(self.old[HALL, kind])[1]
                for key in ("Door List", "WaypointList"):
                    obj[1][key] = (15, obj[1][key][1][:-2])
                self.old[HALL, kind] = write(signature, obj)
            self.raw = pack_module(self.raw, self.old)
        self.result = expand(self.raw)
        self.new = {(n, k): b for n, k, b in resources(self.result)}

    def test_original_content_and_event_hooks_survive(self):
        allowed = {("module", 2014), (HALL, ARE), (HALL, GIT), (HALL, GIC)}
        for key, value in self.old.items():
            if key not in allowed:
                self.assertEqual(self.new[key], value, key)
        for name, kind, except_fields in (
            ("module", 2014, {"Mod_Area_list"}),
            (HALL, ARE, {"Tile_List"}),
            (HALL, GIT, {"Door List", "WaypointList"}),
        ):
            old = read(self.old[name, kind])[1][1]
            new = read(self.new[name, kind])[1][1]
            self.assertEqual(
                {k: v for k, v in old.items() if k not in except_fields},
                {k: v for k, v in new.items() if k not in except_fields},
            )
        before = read(self.old[HALL, ARE])[1][1]["Tile_List"][1]
        after = read(self.new[HALL, ARE])[1][1]["Tile_List"][1]
        self.assertEqual(
            [i for i in range(len(before)) if before[i] != after[i]], [16, 18]
        )

    def test_all_four_links_reach_unique_waypoints_in_other_areas(self):
        points, doors = {}, []
        for area in (HALL, FOREST, CAVE):
            placed = read(self.new[area, GIT])[1][1]
            for obj in placed["WaypointList"][1]:
                tag = obj[1]["Tag"][1]
                self.assertNotIn(tag, points)
                points[tag] = area
            doors += [(area, obj[1]) for obj in placed["Door List"][1]]
        self.assertEqual(len(doors), 4)
        for area, obj in doors:
            self.assertEqual(obj["LinkedToFlags"], (0, 2))
            self.assertNotEqual(points[obj["LinkedTo"][1]], area)
            self.assertFalse(obj["Locked"][1])
            self.assertFalse(obj["TrapFlag"][1])

    def test_new_areas_have_valid_tile_counts_and_no_armed_encounters(self):
        for area, tileset, flags in ((FOREST, b"ttf01", 4), (CAVE, b"tdm01", 7)):
            fields = read(self.new[area, ARE])[1][1]
            self.assertEqual(fields["Tileset"][1], tileset)
            self.assertEqual(fields["Flags"][1], flags)
            self.assertEqual(
                len(fields["Tile_List"][1]), fields["Width"][1] * fields["Height"][1]
            )
            placed = read(self.new[area, GIT])[1][1]
            comments = read(self.new[area, GIC])[1][1]
            for key in ("Creature List", "Encounter List", "TriggerList"):
                self.assertEqual(placed[key][1], [])
            for key, (kind, value) in placed.items():
                if kind == 15:
                    self.assertEqual(len(value), len(comments[key][1]), key)

    def test_refuses_overwriting_existing_area_or_changed_doorway_tile(self):
        with self.assertRaisesRegex(ValueError, "already exist"):
            expand(self.result)
        changed = copy.deepcopy(self.old)
        hall = read(changed[HALL, ARE])[1]
        hall[1]["Tile_List"][1][16][1]["Tile_ID"] = (5, 999)
        changed[HALL, ARE] = write(b"ARE V3.2", hall)
        with self.assertRaisesRegex(ValueError, "edited"):
            expand(pack_module(self.raw, changed))
