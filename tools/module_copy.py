"""Create a development COPY of an ERF module; preserve its original load script.

The original module is never written. No third-party module is distributed.
"""

import argparse
import struct
from pathlib import Path


def resources(raw):
    if raw[:8] not in (b"MOD V1.0", b"ERF V1.0"):
        raise ValueError("Expected an ERF V1.0 module")
    count, key_offset, resource_offset = struct.unpack_from("<I4xII", raw, 16)
    entries = []
    for i in range(count):
        name, resource_id, kind, _ = struct.unpack_from(
            "<16sIHH", raw, key_offset + i * 24
        )
        offset, size = struct.unpack_from("<II", raw, resource_offset + resource_id * 8)
        if offset + size > len(raw):
            raise ValueError("Invalid ERF resource bounds")
        entries.append(
            (name.rstrip(b"\0").decode("ascii"), kind, raw[offset : offset + size])
        )
    return entries


def replace_resref(gff, label, replacement):
    numbers = list(struct.unpack_from("<12I", gff, 8))
    sizes = [12, 12, 16, 1, 1, 1]
    blocks = [
        bytearray(gff[numbers[i * 2] : numbers[i * 2] + numbers[i * 2 + 1] * sizes[i]])
        for i in range(6)
    ]
    labels = [
        bytes(blocks[2][i : i + 16]).rstrip(b"\0").decode("ascii")
        for i in range(0, len(blocks[2]), 16)
    ]
    old = None
    for i in range(0, len(blocks[1]), 12):
        kind, index, offset = struct.unpack_from("<III", blocks[1], i)
        if labels[index] == label:
            if kind != 11:
                raise ValueError("Expected ResRef field")
            length = blocks[3][offset]
            old = bytes(blocks[3][offset + 1 : offset + 1 + length]).decode("ascii")
            data = replacement.encode("ascii")
            struct.pack_into("<I", blocks[1], i + 8, len(blocks[3]))
            blocks[3].extend(bytes([len(data)]) + data)
            break
    if old is None:
        raise ValueError("Module field not found: " + label)
    header = bytearray(gff[:56])
    pos = 56
    for i, block in enumerate(blocks):
        struct.pack_into("<II", header, 8 + i * 8, pos, len(block) // sizes[i])
        pos += len(block)
    return bytes(header) + b"".join(blocks), old


def simple_fields(gff):
    """Read scalar fields needed to locate the module entrance."""
    _, _, fields, count, labels, _, data, _, _, _, _, _ = struct.unpack_from(
        "<12I", gff, 8
    )
    result = {}
    for i in range(count):
        kind, label, value = struct.unpack_from("<III", gff, fields + i * 12)
        name = (
            gff[labels + label * 16 : labels + label * 16 + 16]
            .rstrip(b"\0")
            .decode("ascii")
        )
        if kind == 8:
            result[name] = struct.unpack("<f", struct.pack("<I", value))[0]
        elif kind == 11:
            length = gff[data + value]
            result[name] = gff[data + value + 1 : data + value + 1 + length].decode(
                "ascii"
            )
        elif kind == 10:
            length = struct.unpack_from("<I", gff, data + value)[0]
            result[name] = gff[data + value + 4 : data + value + 4 + length].decode(
                "cp1252"
            )
    return result


def make_copy(source, target, load_script="rw_load", chat_script=None):
    if source.resolve() == target.resolve() or target.exists():
        raise ValueError(
            "Choose a new output path; original and existing files are never overwritten"
        )
    raw = source.read_bytes()
    entries = resources(raw)
    old = None
    for i, (name, kind, data) in enumerate(entries):
        if name == "module" and kind == 2014:
            data, old = replace_resref(data, "Mod_OnModLoad", load_script)
            if chat_script:
                data, _ = replace_resref(data, "Mod_OnPlrChat", chat_script)
            entries[i] = (name, kind, data)
    if old is None:
        raise ValueError("module.ifo not found")
    loc_size, loc_offset = struct.unpack_from("<I4xI", raw, 12)
    localized = raw[loc_offset : loc_offset + loc_size]
    count = len(entries)
    header = bytearray(raw[:160])
    keys_offset = 160 + len(localized)
    resource_offset = keys_offset + count * 24
    data_offset = resource_offset + count * 8
    struct.pack_into("<III", header, 20, 160, keys_offset, resource_offset)
    keys, index, content = bytearray(), bytearray(), bytearray()
    for i, (name, kind, data) in enumerate(entries):
        keys.extend(struct.pack("<16sIHH", name.encode(), i, kind, 0))
        index.extend(struct.pack("<II", data_offset + len(content), len(data)))
        content.extend(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(header + localized + keys + index + content)
    return old


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    previous = make_copy(args.source, args.target)
    wrapper = "void main() {\n"
    if previous:
        wrapper += '    ExecuteScript("' + previous + '", OBJECT_SELF);\n'
    wrapper += '    ExecuteScript("rw_init", GetModule());\n}\n'
    args.target.with_suffix(".rw_load.nss").write_text(wrapper)
    print("Created module copy; preserved load handler:", previous or "(none)")
