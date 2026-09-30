"""Add forest/cave encounter stages to a COPY of the edited Crown Hall demo.

Uses stock NWN tiles and ordinary linked doors. No HAK, new game script, running
server or Role Weaver database is required. Existing authored objects and module
event hooks are preserved. Reruns refuse existing destination areas so later
Aurora edits can never be silently replaced by this generator.
"""

import argparse
from collections import OrderedDict
import copy
import math
from pathlib import Path
import struct

if __package__:
    from .gff import read, write, text
    from .module_copy import resources
else:
    from gff import read, write, text
    from module_copy import resources

HALL = "throne_room"
FOREST = "rw_forest"
CAVE = "rw_cave"
ARE, GIT, GIC = 2012, 2023, 2046


def node(kind, **fields):
    return kind, OrderedDict(fields)


def set_value(obj, key, value, kind=None):
    obj[1][key] = (obj[1][key][0] if kind is None else kind, value)


def pack_module(raw, entries):
    """Repack the ERF container, retaining its header and localized description."""
    header = bytearray(raw[:160])
    size, offset = struct.unpack_from("<I4xI", raw, 12)
    localized = raw[offset : offset + size]
    keys_at = 160 + size
    index_at = keys_at + 24 * len(entries)
    payload_at = index_at + 8 * len(entries)
    struct.pack_into("<4I", header, 16, len(entries), 160, keys_at, index_at)
    keys, index, payload = bytearray(), bytearray(), bytearray()
    for i, ((name, kind), data) in enumerate(entries.items()):
        if len(name.encode("ascii")) > 16:
            raise ValueError("Resource name exceeds NWN's 16-character limit")
        keys.extend(struct.pack("<16sIHH", name.encode("ascii"), i, kind, 0))
        index.extend(struct.pack("<II", payload_at + len(payload), len(data)))
        payload.extend(data)
    return bytes(header) + localized + keys + index + payload


def tile(template, ident, orientation=0):
    result = copy.deepcopy(template)
    for key, value in {
        "Tile_ID": ident,
        "Tile_Orientation": orientation,
        "Tile_Height": 0,
    }.items():
        set_value(result, key, value)
    return result


def rotate_corners(corners):
    """Rotate NW, NE, SW, SE corners counterclockwise by 90 degrees."""
    nw, ne, sw, se = corners
    return ne, se, nw, sw


def terrain_grid(template, width, height, vertices, forest=False):
    """Match terrain corners, so adjacent stock tiles have continuous edges.

    Forest: ttf01 Forest/Cliff. Cave: tdm01 Floor/Wall. True vertices are the
    walkable terrain. Only simple, verified stock tile variants are used.
    """
    candidates = [
        ((False, False, False, False), 6 if forest else 5),
        # Cave tile 4 contains a central rock pillar. Tile 103 is clear floor.
        ((True, True, True, True), 5 if forest else 103),
        ((False, False, True, False), 0),
        ((True, False, True, False), 1),
        ((False, True, True, True), 3),
    ]
    result = []
    for y in range(height):
        for x in range(width):
            wanted = tuple(
                p in vertices for p in ((x, y + 1), (x + 1, y + 1), (x, y), (x + 1, y))
            )
            match = None
            for corners, ident in candidates:
                for rotation in range(4):
                    if corners == wanted:
                        match = tile(template, ident, rotation)
                        break
                    corners = rotate_corners(corners)
                if match is not None:
                    break
            if match is None:
                raise ValueError(f"Unsupported terrain corners at {x}, {y}")
            result.append(match)
    return result


def waypoint(tag, name, x, y, facing=90, map_note=False):
    angle = math.radians(facing)
    return node(
        5,
        Appearance=(0, 0),
        Description=(12, text(name)),
        LinkedTo=(10, b""),
        LocalizedName=(12, text(name)),
        HasMapNote=(0, int(map_note)),
        MapNoteEnabled=(0, int(map_note)),
        MapNote=(12, text(name)),
        Tag=(10, tag.encode()),
        TemplateResRef=(11, b""),
        XPosition=(8, x),
        YPosition=(8, y),
        ZPosition=(8, 0.0),
        XOrientation=(8, math.cos(angle)),
        YOrientation=(8, math.sin(angle)),
    )


def door(tag, name, target, x, y, bearing, appearance=0, opened=False):
    """A native transition to a safe arrival waypoint, using NWN's default click handler."""
    result = node(8)
    for field in (
        "AutoRemoveKey",
        "CloseLockDC",
        "DisarmDC",
        "Fort",
        "Hardness",
        "KeyRequired",
        "Lockable",
        "Locked",
        "OpenLockDC",
        "Ref",
        "TrapDetectable",
        "TrapDetectDC",
        "TrapDisarmable",
        "TrapFlag",
        "TrapOneShot",
        "TrapType",
        "Will",
    ):
        set_value(result, field, 0, 0)
    for field in (
        "Conversation",
        "OnClosed",
        "OnDamaged",
        "OnDeath",
        "OnDisarm",
        "OnHeartbeat",
        "OnLock",
        "OnMeleeAttacked",
        "OnOpen",
        "OnSpellCastAt",
        "OnTrapTriggered",
        "OnUnlock",
        "OnUserDefined",
        "OnClick",
        "OnFailToOpen",
    ):
        set_value(result, field, b"", 11)
    for field, (kind, value) in {
        "AnimationState": (0, int(opened)),
        "Appearance": (4, appearance),
        "GenericType": (0, 1),
        "CurrentHP": (3, 100),
        "HP": (3, 100),
        "Description": (12, text(name)),
        "Faction": (4, 1),
        "Interruptable": (0, 1),
        "LocName": (12, text(name)),
        "Plot": (0, 1),
        "PortraitId": (2, 0),
        "Tag": (10, tag.encode()),
        "TemplateResRef": (11, b""),
        "KeyName": (10, b""),
        "LinkedTo": (10, target.encode()),
        "LinkedToFlags": (0, 2),
        "LoadScreenID": (2, 0),
        "Bearing": (8, math.radians(bearing)),
        "X": (8, x),
        "Y": (8, y),
        "Z": (8, 0.0),
    }.items():
        set_value(result, field, value, kind)
    return result


def empty_objects(hall, outdoor):
    result = copy.deepcopy(hall)
    for key, (kind, _) in result[1].items():
        if kind == 15:
            result[1][key] = kind, []
    properties = result[1]["AreaProperties"][1]
    set_value(properties, "EnvAudio", 0)
    set_value(properties, "AmbientSndDay", 49 if outdoor else 60)
    set_value(properties, "AmbientSndNight", 53 if outdoor else 60)
    set_value(properties, "MusicDay", 4 if outdoor else 9)
    set_value(properties, "MusicNight", 6 if outdoor else 10)
    set_value(properties, "MusicBattle", 35 if outdoor else 37)
    return result


def comments_for(objects):
    """Aurora expects one comment entry per placed object, even for empty comments."""
    return (
        0xFFFFFFFF,
        OrderedDict(
            (key, (15, [node(obj[0], Comment=(10, b"")) for obj in value]))
            for key, (kind, value) in objects[1].items()
            if kind == 15
        ),
    )


def new_area(hall, tag, name, tileset, width, height, tiles, outdoor):
    result = copy.deepcopy(hall)
    values = dict(
        Tag=tag.encode(),
        Name=text(name),
        ResRef=tag.encode(),
        Tileset=tileset.encode(),
        Width=width,
        Height=height,
        Tile_List=tiles,
        Flags=4 if outdoor else 7,
        Version=1,
        Comments=b"Editable Role Weaver encounter staging area.",
        DayNightCycle=0,
        IsNight=0 if outdoor else 1,
        LightingScheme=0 if outdoor else 13,
        SkyBox=1 if outdoor else 0,
        SunAmbientColor=0x94A090,
        SunDiffuseColor=0xD4E3F0,
        MoonAmbientColor=0x58646A,
        MoonDiffuseColor=0x809098,
        SunShadows=int(outdoor),
        MoonShadows=0,
        SunFogAmount=0,
        MoonFogAmount=0,
        ChanceRain=0,
        ChanceSnow=0,
        ChanceLightning=0,
        WindPower=1 if outdoor else 0,
        LoadScreenID=0,
        FogClipDist=70.0,
    )
    for key, value in values.items():
        set_value(result, key, value)
    for key in ("OnEnter", "OnExit", "OnHeartbeat", "OnUserDefined"):
        set_value(result, key, b"")
    return result


def expand(raw):
    entries = {(n, k): b for n, k, b in resources(raw)}
    original = dict(entries)
    if any(
        (name, kind) in entries for name in (FOREST, CAVE) for kind in (ARE, GIT, GIC)
    ):
        raise ValueError(
            "Encounter areas already exist; edit them in Aurora instead of regenerating"
        )
    module = read(entries["module", 2014])[1]
    hall = read(entries[HALL, ARE])[1]
    objects = read(entries[HALL, GIT])[1]
    comments = read(entries[HALL, GIC])[1]
    if (hall[1]["Tileset"][1], hall[1]["Width"][1], hall[1]["Height"][1]) != (
        b"tic01",
        5,
        7,
    ):
        raise ValueError(
            "Expected the 5 by 7 Crown Hall; review changed geometry before adding doors"
        )
    # These two wall segments are halfway along the hall. Swap only their models
    # for matching Rich doorway tiles, retaining terrain edges and orientation.
    for index, orientation in ((16, 2), (18, 0)):
        current = hall[1]["Tile_List"][1][index]
        if (current[1]["Tile_ID"][1], current[1]["Tile_Orientation"][1]) != (
            149,
            orientation,
        ):
            raise ValueError(
                "The proposed hall doorway tile has been edited; refusing to overwrite it"
            )
        set_value(current, "Tile_ID", 121)
    hall_doors = [
        door("rw_hall_forest", "Forest Path", "rw_arr_forest", 12.51, 35.0, 90),
        door("rw_hall_cave", "Troll Cave", "rw_arr_cave", 37.49, 35.0, 270),
    ]
    hall_points = [
        waypoint("rw_arr_hall_w", "Crown Hall: forest door", 16.0, 33.0, 0),
        waypoint("rw_arr_hall_e", "Crown Hall: cave door", 34.0, 33.0, 180),
    ]
    objects[1]["Door List"][1].extend(hall_doors)
    objects[1]["WaypointList"][1].extend(hall_points)
    comments[1]["Door List"][1].extend(
        node(8, Comment=(10, b"Encounter area transition")) for _ in hall_doors
    )
    comments[1]["WaypointList"][1].extend(
        node(5, Comment=(10, b"Keep this arrival clear")) for _ in hall_points
    )
    template = hall[1]["Tile_List"][1][0]
    # A 50 x 70 metre valley: a southern return point and a northbound path,
    # with open space off the path for a robbery and room to retreat.
    vertices = {(x, y) for x in range(1, 5) for y in range(2, 6)}
    forest_tiles = terrain_grid(template, 5, 7, vertices, forest=True)
    forest_tiles[7] = tile(template, 81, 3)  # South-facing Forest Exit hook.
    for y in (2, 3):
        forest_tiles[y * 5 + 2] = tile(template, 25)
    forest_tiles[22] = tile(template, 28, 2)  # End the road in the clearing.
    forest_tiles[13] = tile(template, 167)  # Trees beside the path, not on it.
    forest_tiles[21] = tile(template, 167, 2)
    forest = new_area(
        hall, FOREST, "Crownwood Forest Path", "ttf01", 5, 7, forest_tiles, True
    )
    forest_objects = empty_objects(objects, outdoor=True)
    forest_objects[1]["Door List"][1].append(
        door(
            "rw_forest_hall",
            "Return to Crown Hall",
            "rw_arr_hall_w",
            25.0,
            14.2,
            180,
            appearance=54,
            opened=True,
        )
    )
    forest_objects[1]["WaypointList"][1].extend(
        [
            waypoint(
                "rw_arr_forest", "Return to Crown Hall", 25.0, 18.0, map_note=True
            ),
            waypoint("rw_rob_trigger", "Robbery: approach", 25.0, 27.0),
            waypoint("rw_rob_stage", "Robbery: confrontation", 25.0, 35.0, 270),
            waypoint("rw_rob_left", "Robbery: left lookout", 20.0, 37.0, 315),
            waypoint("rw_rob_right", "Robbery: right lookout", 30.0, 37.0, 225),
            waypoint("rw_rob_retreat", "Robbery: retreat destination", 25.0, 46.0),
        ]
    )
    # Four clear floor tiles instead of the original nine: roughly half the
    # playable space, with the same entrance and room to move around the cast.
    cave_vertices = {(x, y) for x in range(1, 4) for y in range(2, 5)}
    cave_tiles = terrain_grid(template, 4, 5, cave_vertices)
    cave_tiles[6] = tile(template, 116, 2)  # South-facing Mines exit door.
    cave = new_area(hall, CAVE, "Hollowstone Cave", "tdm01", 4, 5, cave_tiles, False)
    cave_objects = empty_objects(objects, outdoor=False)
    cave_objects[1]["Door List"][1].append(
        door(
            "rw_cave_hall",
            "Return to Crown Hall",
            "rw_arr_hall_e",
            25.0,
            14.5,
            180,
            appearance=52,
        )
    )
    cave_objects[1]["WaypointList"][1].extend(
        [
            waypoint("rw_arr_cave", "Return to Crown Hall", 25.0, 18.0, map_note=True),
            waypoint("rw_troll_trigger", "Troll encounter: approach", 25.0, 24.0),
            waypoint("rw_troll_grust", "Grust staging point", 18.0, 28.0, 270),
            waypoint("rw_troll_morga", "Morga staging point", 26.0, 29.0, 270),
            waypoint("rw_troll_hostage", "Elana Voss staging point", 22.0, 36.0, 270),
            waypoint("rw_troll_escape", "Hostage escape destination", 25.0, 20.0, 270),
        ]
    )
    for tag, area, placed in (
        (FOREST, forest, forest_objects),
        (CAVE, cave, cave_objects),
    ):
        entries[tag, ARE] = write(b"ARE V3.2", area)
        entries[tag, GIT] = write(b"GIT V3.2", placed)
        entries[tag, GIC] = write(b"GIC V3.2", comments_for(placed))
        module[1]["Mod_Area_list"][1].append(node(6, Area_Name=(11, tag.encode())))
    entries["module", 2014] = write(b"IFO V3.2", module)
    entries[HALL, ARE] = write(b"ARE V3.2", hall)
    entries[HALL, GIT] = write(b"GIT V3.2", objects)
    entries[HALL, GIC] = write(b"GIC V3.2", comments)
    changed = {("module", 2014), (HALL, ARE), (HALL, GIT), (HALL, GIC)}
    if any(
        entries[key] != value for key, value in original.items() if key not in changed
    ):
        raise ValueError("Unexpected change outside area integration")
    result = pack_module(raw, entries)
    if {(n, k): b for n, k, b in resources(result)} != entries:
        raise ValueError("Module container verification failed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve() == args.module.resolve():
        parser.error(
            "Choose a new output path; source and existing files are never overwritten"
        )
    result = expand(args.module.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print(f"Expanded module ready: {args.output}")


if __name__ == "__main__":
    main()
