"""Build a copy of the supplied Crown Hall module; never modify the input.

Compile scripts/ first against the world's bridge and matching NWNX headers.
This builder preserves unrelated module resources byte for byte.
"""

import argparse, copy, json, struct
from pathlib import Path
from collections import OrderedDict
from gff_tools import read, write, text
from session_hooks import install as install_session_hooks


def unpack(raw):
    assert raw[:8] == b"MOD V1.0"
    count, ko, ro = struct.unpack_from("<I4xII", raw, 16)
    result = {}
    for i in range(count):
        name, rid, kind, _ = struct.unpack_from("<16sIHH", raw, ko + 24 * i)
        off, size = struct.unpack_from("<II", raw, ro + 8 * rid)
        result[name.rstrip(b"\0").decode(), kind] = raw[off : off + size]
    return result


def pack(raw, entries):
    header = bytearray(raw[:160])
    locsize = struct.unpack_from("<I", raw, 12)[0]
    lo = struct.unpack_from("<I", raw, 20)[0]
    localized = raw[lo : lo + locsize]
    ko = 160 + len(localized)
    ro = ko + 24 * len(entries)
    do = ro + 8 * len(entries)
    struct.pack_into("<4I", header, 16, len(entries), 160, ko, ro)
    keys = bytearray()
    indexes = bytearray()
    payload = bytearray()
    for i, ((name, kind), data) in enumerate(entries.items()):
        assert len(name) <= 16
        keys.extend(struct.pack("<16sIHH", name.encode(), i, kind, 0))
        indexes.extend(struct.pack("<II", do + len(payload), len(data)))
        payload.extend(data)
    return bytes(header) + localized + keys + indexes + payload


def put(node, key, value, kind=None):
    node[1][key] = (node[1][key][0] if kind is None else kind, value)


def node(fields, typ=0):
    return (typ, OrderedDict(fields))


def build(source, base, compiled, output):
    if output.exists() or output.resolve() == source.resolve():
        raise ValueError("Use a new output filename")
    raw = source.read_bytes()
    entries = unpack(raw)
    original = dict(entries)
    _, mod = read(entries["module", 2014])
    _, git = read(entries["throne_room", 2023])
    for key, expected, new in [
        ("Mod_OnModLoad", b"rw_worldload", b"rq_load"),
        ("Mod_OnPlrChat", b"rw_worldchat", b"rq_chat"),
    ]:
        if mod[1][key][1] != expected:
            raise ValueError("Unexpected existing hook: " + key)
        put(mod, key, new)
    install_session_hooks(mod)
    entries["module", 2014] = write(b"IFO V3.2", mod)
    _, creature = read(base.read_bytes())
    content = json.loads(Path(__file__).with_name("content.json").read_text())
    for profile in content["profiles"]:
        c = copy.deepcopy(creature)
        id = profile["id"]
        for key, (kind, value) in list(c[1].items()):
            if key.startswith("Script"):
                put(c, key, b"")
        for key, value in [
            ("TemplateResRef", id.encode()),
            ("Tag", id.encode()),
            ("FirstName", text(profile["name"])),
            ("LastName", text("")),
            ("Conversation", b""),
            ("Appearance_Type", int(profile["appearance"])),
            ("Gender", int(profile["gender"])),
            ("Plot", 1),
            ("IsImmortal", 1),
            ("FactionID", 2),
        ]:
            put(c, key, value)
        put(
            c,
            "ClassList",
            [
                node(
                    [
                        ("Class", (5, int(profile["npc_class"]))),
                        ("ClassLevel", (3, int(profile["level"]))),
                    ],
                    2,
                )
            ],
        )
        entries[id, 2027] = write(b"UTC V3.2", c)
        if id != "rq_king":
            for key, val in [
                ("XPosition", float(profile["x"])),
                ("YPosition", float(profile["y"])),
                ("ZPosition", 0.0),
                ("XOrientation", 0.0),
                ("YOrientation", 1.0),
            ]:
                put(c, key, val, 8)
            git[1]["Creature List"][1].append((4, c[1]))
    template = git[1]["Placeable List"][1][0]
    # The existing throne must be dynamic and usable for ActionSit.
    throne = next(
        p for p in git[1]["Placeable List"][1] if p[1]["Appearance"][1] == 183
    )
    put(throne, "Tag", b"rq_throne")
    put(throne, "Static", 0)
    put(throne, "Useable", 1)
    props = [
        ("rq_board", "Royal Investigator Noticeboard", 87, 21.0, 19.0, True),
        ("rq_table", "Visitor Table", 97, 17.0, 30.0, False),
        ("rq_stall", "Merchant Stall", 288, 17.0, 38.0, False),
        ("rq_study", "Arcane Study", 303, 33.0, 38.0, False),
        ("rq_shrine", "Shrine of Mercy", 97, 33.0, 48.0, False),
        ("rq_candle", "Shrine Candle", 383, 33.0, 48.0, False),
    ]
    for tag, name, appearance, x, y, usable in props:
        p = copy.deepcopy(template)
        for key, (kind, value) in list(p[1].items()):
            if key.startswith("On") or key in ("Conversation", "TemplateResRef"):
                put(p, key, b"")
        for key, value in [
            ("Tag", tag.encode()),
            ("LocName", text(name)),
            ("Appearance", appearance),
            ("X", x),
            ("Y", y),
            ("Z", 0.0 if tag != "rq_candle" else 1.0),
            ("Bearing", 0.0),
            ("Static", int(not usable)),
            ("Useable", int(usable)),
            ("HasInventory", 0),
            ("Plot", 1),
        ]:
            put(p, key, value)
        if usable:
            put(p, "OnUsed", b"rq_board", 11)
            put(
                p,
                "Description",
                text(Path(__file__).with_name("noticeboard.txt").read_text()),
                12,
            )
        git[1]["Placeable List"][1].append(p)
    entries["throne_room", 2023] = write(b"GIT V3.2", git)
    for path in sorted(Path(__file__).with_name("scripts").glob("rq_*.nss")):
        entries[path.stem, 2009] = path.read_bytes()
        if path.stem == "rq_inc":
            continue
        entries[path.stem, 2010] = (compiled / (path.stem + ".ncs")).read_bytes()
    result = pack(raw, entries)
    assert unpack(result) == entries
    changed = {("module", 2014), ("throne_room", 2023)}
    assert all(entries[k] == v for k, v in original.items() if k not in changed)
    for (name, kind), value in entries.items():
        if kind in (2014, 2023, 2027, 2029):
            signature, g = read(value)
            assert read(write(signature, g)) == (signature, g)
    output.write_bytes(result)
    print(
        f"Built {output}: {len(entries)} resources; {len(original)-2} original resources preserved byte-for-byte"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--module", type=Path, required=True)
    p.add_argument("--creature", type=Path, required=True)
    p.add_argument("--compiled", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    build(a.module, a.creature, a.compiled, a.output)
