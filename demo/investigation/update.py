"""Update only quest scripts and the noticeboard in an existing investigation.

Preserve the area's other objects, placements and module hooks. Write a new
module file so the server owner can back up and replace the live copy safely.
"""

import argparse
from pathlib import Path

from build import pack, put, unpack
from gff_tools import read, text, write
from session_hooks import install as install_session_hooks


def update(source, compiled, output):
    if output.exists() or source.resolve() == output.resolve():
        raise ValueError("Choose a new output module filename")
    original = source.read_bytes()
    entries = unpack(original)
    previous = dict(entries)
    _, module = read(entries["module", 2014])
    if module[1]["Mod_OnPlrChat"][1] != b"rq_chat":
        raise ValueError("This module does not have the investigation chat hook")
    install_session_hooks(module)
    entries["module", 2014] = write(b"IFO V3.2", module)
    signature, area = read(entries["throne_room", 2023])
    boards = [
        obj for obj in area[1]["Placeable List"][1] if obj[1]["Tag"][1] == b"rq_board"
    ]
    if len(boards) != 1:
        raise ValueError("Expected exactly one investigation noticeboard")
    description = Path(__file__).with_name("noticeboard.txt").read_text()
    put(boards[0], "Description", text(description), 12)
    entries["throne_room", 2023] = write(signature, area)
    changed = {("throne_room", 2023), ("module", 2014)}
    # Remove the retired native court menus and their callbacks.
    retired = [
        "rq_case_clear",
        "rq_case_status",
        "rq_court_end",
        "rq_has_1",
        "rq_has_16",
        "rq_has_2",
        "rq_has_4",
        "rq_has_8",
        "rq_pick_1",
        "rq_pick_16",
        "rq_pick_2",
        "rq_pick_4",
        "rq_pick_8",
        "rq_submit",
        "rq_s_cleric",
        "rq_s_guard",
        "rq_s_holt",
        "rq_s_innkeep",
        "rq_s_merchant",
        "rq_s_wizard",
        "rq_confirm",
        "rq_evidence",
    ]
    removed = {key for key in entries if key[0] in retired}
    for key in removed:
        del entries[key]
    changed.update(removed)
    for script in sorted(Path(__file__).with_name("scripts").glob("rq_*.nss")):
        entries[script.stem, 2009] = script.read_bytes()
        changed.add((script.stem, 2009))
        if script.stem != "rq_inc":
            entries[script.stem, 2010] = (
                compiled / (script.stem + ".ncs")
            ).read_bytes()
            changed.add((script.stem, 2010))
    result = pack(original, entries)
    assert unpack(result) == entries
    assert all(
        entries[key] == value for key, value in previous.items() if key not in changed
    )
    output.write_bytes(result)
    print(
        "Updated investigation scripts and noticeboard; unrelated resources preserved:",
        output,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--compiled", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    update(args.module, args.compiled, args.output)
