"""Add one ordinary dialogue NPC to a COPY of a module; preserve existing content.

The NPC stands three metres right and two metres forward of the module entrance.
Move it in Aurora afterward if desired. Re-running updates this NPC in place;
other creatures, placeables, scripts, events, inventories and layout stay intact.
The output must be a new file. This tool never stops or updates a running server.
"""

import argparse
import copy
import struct
from pathlib import Path

if __package__:
    from .build_translation_demo import ROOT, build_creature, read, write
    from .module_copy import resources
else:
    from build_translation_demo import ROOT, build_creature, read, write
    from module_copy import resources


def add_guide(raw, blueprint, dialogue):
    entries = {(n, k): d for n, k, d in resources(raw)}
    original = dict(entries)
    mod = read(entries["module", 2014])[1][1]
    area = mod["Mod_Entry_Area"][1].decode("ascii")
    signature, git = read(entries[area, 2023])
    before = copy.deepcopy(git)
    creature = read(blueprint)[1][1]
    x, y = mod["Mod_Entry_X"][1], mod["Mod_Entry_Y"][1]
    # The test world's entrance faces north. Keep the guide beside the arrival point.
    dx, dy = (
        mod.get("Mod_Entry_Dir_X", (8, 0.0))[1],
        mod.get("Mod_Entry_Dir_Y", (8, 1.0))[1],
    )
    creature.update(
        XPosition=(8, x + 3 * dy + 2 * dx),
        YPosition=(8, y - 3 * dx + 2 * dy),
        ZPosition=mod["Mod_Entry_Z"],
        XOrientation=(8, -dy),
        YOrientation=(8, dx),
    )
    old = git[1].get("Creature List", (15, []))[1]
    matches = [
        i for i, n in enumerate(old) if n[1].get("Tag", (10, b""))[1] == b"rw_tr_guide"
    ]
    if len(matches) > 1:
        raise ValueError("Multiple Royal Guides found; choose which one to keep first")
    kept = copy.deepcopy(old)
    if matches:
        # Preserve the owner's position, facing, inventory and other authored
        # properties. A refreshed blueprint alone cannot update a placed NPC.
        fields = kept[matches[0]][1]
        for key in (
            "Appearance_Type",
            "Gender",
            "Race",
            "Description",
            "Conversation",
            "ScriptDialogue",
        ):
            fields[key] = creature[key]
    else:
        kept.append((4, creature))
    git[1]["Creature List"] = (15, kept)
    entries[area, 2023] = write(signature, git)
    if (area, 2046) in entries:
        gic_signature, gic = read(entries[area, 2046])
        comments = gic[1].get("Creature List", (15, []))[1]
        if len(comments) > len(kept):
            raise ValueError("Creature comments do not match the area's creatures")
        gic[1]["Creature List"] = (
            15,
            comments
            + [(0, {"Comment": (10, b"")}) for _ in range(len(kept) - len(comments))],
        )
        entries[area, 2046] = write(gic_signature, gic)
    entries["rw_tr_guide", 2027] = blueprint
    entries["rw_tr_demo", 2029] = dialogue
    # Refuse any accidental change outside the guide and its two new resources.
    assert all(
        entries[k] == v
        for k, v in original.items()
        if k
        not in {(area, 2023), (area, 2046), ("rw_tr_guide", 2027), ("rw_tr_demo", 2029)}
    )
    assert {k: v for k, v in git[1].items() if k != "Creature List"} == {
        k: v for k, v in before[1].items() if k != "Creature List"
    }
    header = bytearray(raw[:160])
    loc_size, loc_offset = struct.unpack_from("<I4xI", raw, 12)
    localized = raw[loc_offset : loc_offset + loc_size]
    count = len(entries)
    ko = 160 + len(localized)
    ro, data_offset = ko + count * 24, ko + count * 32
    struct.pack_into("<4I", header, 16, count, 160, ko, ro)
    keys, index, content = bytearray(), bytearray(), bytearray()
    for i, ((name, kind), data) in enumerate(entries.items()):
        keys.extend(struct.pack("<16sIHH", name.encode(), i, kind, 0))
        index.extend(struct.pack("<II", data_offset + len(content), len(data)))
        content.extend(data)
    result = bytes(header) + localized + keys + index + content
    assert {(n, k): d for n, k, d in resources(result)} == entries
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.module.resolve() == args.output.resolve():
        parser.error(
            "Choose a new output file; input and existing files are never overwritten"
        )
    args.output.write_bytes(
        add_guide(
            args.module.read_bytes(),
            build_creature((ROOT / "assets/rw_base.utc").read_bytes()),
            (ROOT / "assets/rw_tr_demo.dlg").read_bytes(),
        )
    )
    print("Module copy with Royal Guide:", args.output)
