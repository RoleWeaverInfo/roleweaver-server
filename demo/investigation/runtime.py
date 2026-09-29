"""Rebind the edited investigation to an isolated demo namespace.

Never rebuild area contents: retain every non-script resource from the owner's
module. Compile before the caller installs any game files.
"""

import struct
import subprocess
from pathlib import Path
from build_addon import settings
from module_copy import resources
from prepare_addon import ENTRIES, INCLUDES

ROOT = Path(__file__).resolve().parents[2]
ASSET_TYPES = {".utc": 2027, ".utm": 2051, ".dlg": 2029}


def refresh_bridge(entries):
    """Replace only managed bridge resources, preserving authored world content.

    The editable module can contain older scripts. Never let those silently win
    over the bridge shipped with the application during a demo rebuild.
    """
    for name in (*ENTRIES, *INCLUDES):
        entries[name, 2009] = (ROOT / "bridge" / (name + ".nss")).read_bytes()
    for path in sorted((ROOT / "assets").iterdir()):
        if path.suffix in ASSET_TYPES:
            entries[path.stem, ASSET_TYPES[path.suffix]] = path.read_bytes()


def pack(raw, entries):
    header = bytearray(raw[:160])
    size = struct.unpack_from("<I", raw, 12)[0]
    offset = struct.unpack_from("<I", raw, 20)[0]
    localized = raw[offset : offset + size]
    key_offset = 160 + size
    resource_offset = key_offset + 24 * len(entries)
    data_offset = resource_offset + 8 * len(entries)
    struct.pack_into("<4I", header, 16, len(entries), 160, key_offset, resource_offset)
    keys, indexes, payload = bytearray(), bytearray(), bytearray()
    for i, ((name, kind), data) in enumerate(entries.items()):
        keys.extend(struct.pack("<16sIHH", name.encode(), i, kind, 0))
        indexes.extend(struct.pack("<II", data_offset + len(payload), len(data)))
        payload.extend(data)
    return bytes(header) + localized + keys + indexes + payload


def build_investigation(source, bundle, native, compiler, world, prefix, seed=None):
    raw = source.read_bytes()
    entries = {(name, kind): data for name, kind, data in resources(raw)}
    original = dict(entries)
    if ("rq_load", 2009) not in entries or ("rq_enter", 2010) not in entries:
        raise ValueError("Investigation module is missing its load/login scripts")
    refresh_bridge(entries)
    managed_assets = {
        (p.stem, ASSET_TYPES[p.suffix])
        for p in (ROOT / "assets").iterdir()
        if p.suffix in ASSET_TYPES
    }
    bridge = bundle / "bridge"
    compiled = bundle / "compiled"
    bridge.mkdir(parents=True)
    compiled.mkdir()
    entries["rw_settings", 2009] = settings(world, prefix, "world", "module").encode()
    load = entries["rq_load", 2009].decode()
    marker = ' DelayCommand(2.0,ExecuteScript("rq_setup",GetModule()));'
    if load.count(marker) != 1:
        raise ValueError(
            "Unrecognized investigation load hook; source module unchanged"
        )
    if seed is not None:
        entries["rq_load", 2009] = load.replace(
            marker,
            marker + '\n DelayCommand(3.0,ExecuteScript("rw_demoseed",GetModule()));',
        ).encode()
        entries["rw_demoseed", 2009] = seed.encode()
    for (name, kind), data in entries.items():
        if kind == 2009:
            (bridge / (name + ".nss")).write_bytes(data)
    entrypoints = sorted(
        {name for name, kind in entries if kind == 2010 and (name, 2009) in entries}
        | set(ENTRIES)
        | ({"rw_demoseed"} if seed is not None else set())
    )
    for name in entrypoints:
        result = subprocess.run(
            [
                str(compiler),
                "-n",
                str(native / "runtime"),
                "-i",
                str(bridge) + ";" + str(native / "nwscripts"),
                str(bridge / (name + ".nss")),
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise ValueError(
                "Compilation failed for "
                + name
                + ":\n"
                + result.stdout.decode(errors="replace")
                + result.stderr.decode(errors="replace")
            )
        bytecode = (bridge / (name + ".ncs")).read_bytes()
        entries[name, 2010] = bytecode
        (compiled / (name + ".ncs")).write_bytes(bytecode)
    # Detect accidental edits to the owner's layout, creatures and other assets.
    assert all(
        entries[key] == data
        for key, data in original.items()
        if key[1] not in (2009, 2010) and key not in managed_assets
    )
    output = bundle / "module" / source.name
    output.parent.mkdir()
    output.write_bytes(pack(raw, entries))
