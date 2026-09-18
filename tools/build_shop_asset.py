"""Generate Role Weaver's original empty, fixed-markup NWN store blueprint."""

from pathlib import Path
import struct


def build():
    fields = []
    labels = []
    data = bytearray()
    lists = bytearray(struct.pack("<I", 0))

    def field(name, kind, value):
        labels.append(name.encode().ljust(16, b"\0"))
        if kind in (10, 11, 12):
            offset = len(data)
            if kind == 10:
                data.extend(struct.pack("<I", len(value)) + value)
            elif kind == 11:
                data.extend(bytes([len(value)]) + value)
            else:
                chunk = (
                    struct.pack("<II", 0xFFFFFFFF, 1)
                    + struct.pack("<II", 0, len(value))
                    + value
                )
                data.extend(struct.pack("<I", len(chunk)) + chunk)
            value = offset
        fields.append(struct.pack("<III", kind, len(labels) - 1, value & 0xFFFFFFFF))

    field("ResRef", 11, b"rw_shop")
    field("LocName", 12, b"Role Weaver Weapons")
    field("Tag", 10, b"rw_shop")
    for k, v in [
        ("MarkUp", 100),
        ("MarkDown", 0),
        ("BM_MarkDown", 0),
        ("IdentifyPrice", -1),
        ("MaxBuyPrice", 0),
        ("StoreGold", -1),
    ]:
        field(k, 5, v)
    field("BlackMarket", 0, 0)
    for k in ("OnOpenStore", "OnStoreClosed"):
        field(k, 11, b"")
    for k in ("WillNotBuy", "WillOnlyBuy", "StoreList"):
        field(k, 15, 0)
    indices = b"".join(struct.pack("<I", i) for i in range(len(fields)))
    blocks = [
        struct.pack("<III", 0xFFFFFFFF, 0, len(fields)),
        b"".join(fields),
        b"".join(labels),
        bytes(data),
        indices,
        bytes(lists),
    ]
    sizes = [12, 12, 16, 1, 1, 1]
    header = bytearray(b"UTM V3.2" + b"\0" * 48)
    offset = 56
    for i, block in enumerate(blocks):
        struct.pack_into("<II", header, 8 + i * 8, offset, len(block) // sizes[i])
        offset += len(block)
    return bytes(header) + b"".join(blocks)


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "assets/rw_shop.utm"
    target.write_bytes(build())
    print(target)
