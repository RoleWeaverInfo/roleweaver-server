"""Add an editable supplies chest to a copy of the Crown Hall demo module.

Uses stock item blueprints, with no load script or repeating inventory refill.
Existing chests and all unrelated resources are preserved.
"""

import argparse
import copy
from pathlib import Path

if __package__:
    from .expand_demo_world import node, pack_module, set_value
    from .gff import read, text, write
    from .module_copy import resources
else:
    from expand_demo_world import node, pack_module, set_value
    from gff import read, text, write
    from module_copy import resources

TAG = b"rq_testchest"
STOCK = (
    "nw_wswss001",  # Short sword
    "nw_wswdg001",  # Dagger
    "nw_it_mpotion001",  # Potion of Cure Light Wounds
    "nw_it_mpotion001",
    "nw_it_medkit001",  # Bandages: native Healer's Kit +1
)


def add_chest(raw):
    entries = {(name, kind): data for name, kind, data in resources(raw)}
    signature, hall = read(entries["throne_room", 2023])
    placed = hall[1]["Placeable List"][1]
    if any(obj[1].get("Tag", (10, b""))[1] == TAG for obj in placed):
        return raw  # Never move, replace or restock an authored chest.
    throne = next(obj for obj in placed if obj[1]["Tag"][1] == b"rq_throne")
    chest = copy.deepcopy(throne)
    for key in chest[1]:
        if key.startswith("On") or key == "Conversation":
            set_value(chest, key, b"")
    for key, kind, value in (
        ("Tag", 10, TAG),
        ("TemplateResRef", 11, b"plc_chest1"),
        ("LocName", 12, text("Royal Supplies Chest")),
        (
            "Description",
            12,
            text(
                "Spare weapons and medical supplies for visiting investigators. "
                "You may borrow these to practise collecting, giving and exchanging "
                "items with your familiar or the hall's willing residents."
            ),
        ),
        ("Appearance", 4, 7),
        ("Static", 0, 0),
        ("Useable", 0, 1),
        ("HasInventory", 0, 1),
        ("Plot", 0, 1),
        ("Locked", 0, 0),
        ("Lockable", 0, 0),
        ("TrapFlag", 0, 0),
        ("X", 8, throne[1]["X"][1] + 3.0),
        ("Y", 8, throne[1]["Y"][1] - 1.0),
        ("Z", 8, throne[1]["Z"][1]),
        ("Bearing", 8, 0.0),
    ):
        set_value(chest, key, value, kind)
    chest[1].pop("VarTable", None)
    set_value(
        chest,
        "ItemList",
        [
            node(
                0,
                InventoryRes=(11, ref.encode("ascii")),
                Repos_PosX=(2, index * 2),
                Repos_PosY=(2, 0),
                Dropable=(0, 1),
            )
            for index, ref in enumerate(STOCK)
        ],
        15,
    )
    placed.append(chest)
    entries["throne_room", 2023] = write(signature, hall)
    if ("throne_room", 2046) in entries:
        signature, comments = read(entries["throne_room", 2046])
        comments[1].setdefault("Placeable List", (15, []))[1].append(
            node(chest[0], Comment=(10, b"Editable demo supplies; no scripted refill."))
        )
        entries["throne_room", 2046] = write(signature, comments)
    return pack_module(raw, entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output file; existing modules are not overwritten.")
    args.output.write_bytes(add_chest(args.module.read_bytes()))
    print(args.output)
