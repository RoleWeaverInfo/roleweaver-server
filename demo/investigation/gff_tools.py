"""Small lossless GFF reader/writer for the standalone throne room build."""

import struct as s
from collections import OrderedDict


def read(raw):
    h = s.unpack_from("<12I", raw, 8)
    so, sc, fo, fc, lo, lc, do, dc, io, ic, lso, lsc = h

    def node(i):
        typ, off, count = s.unpack_from("<III", raw, so + 12 * i)
        fields = OrderedDict()
        ids = (
            []
            if count == 0
            else (
                [off] if count == 1 else s.unpack_from("<" + "I" * count, raw, io + off)
            )
        )
        for fi in ids:
            k, li, v = s.unpack_from("<III", raw, fo + 12 * fi)
            label = raw[lo + 16 * li : lo + 16 * li + 16].split(b"\0")[0].decode()
            if k in (0, 1, 2, 3, 4, 5):
                val = v
            elif k == 8:
                val = s.unpack("<f", s.pack("<I", v))[0]
            elif k in (6, 7, 9):
                val = raw[do + v : do + v + 8]
            elif k in (10, 13):
                n = s.unpack_from("<I", raw, do + v)[0]
                val = raw[do + v + 4 : do + v + 4 + n]
            elif k == 11:
                n = raw[do + v]
                val = raw[do + v + 1 : do + v + 1 + n]
            elif k == 12:
                n = s.unpack_from("<I", raw, do + v)[0]
                val = raw[do + v + 4 : do + v + 4 + n]
            elif k == 14:
                val = node(v)
            elif k == 15:
                n = s.unpack_from("<I", raw, lso + v)[0]
                val = [node(j) for j in s.unpack_from("<" + "I" * n, raw, lso + v + 4)]
            elif k in (16, 17):
                val = raw[do + v : do + v + (16 if k == 16 else 12)]
            else:
                raise ValueError(k)
            fields[label] = (k, val)
        return (typ, fields)

    return raw[:8], node(0)


def write(signature, root):
    nodes = []
    fields = []
    labels = []
    data = bytearray()
    idx = bytearray()
    lists = bytearray()

    def put(raw):
        v = len(data)
        data.extend(raw)
        return v

    def node(n):
        ni = len(nodes)
        nodes.append(None)
        ids = []
        for label, (k, val) in n[1].items():
            if label not in labels:
                labels.append(label)
            if k in (0, 1, 2, 3, 4, 5):
                v = val
            elif k == 8:
                v = s.unpack("<I", s.pack("<f", val))[0]
            elif k in (6, 7, 9, 16, 17):
                v = put(val)
            elif k in (10, 12, 13):
                v = put(s.pack("<I", len(val)) + val)
            elif k == 11:
                v = put(bytes([len(val)]) + val)
            elif k == 14:
                v = node(val)
            elif k == 15:
                children = [node(c) for c in val]
                v = len(lists)
                lists.extend(
                    s.pack("<I", len(children))
                    + s.pack("<" + "I" * len(children), *children)
                )
            ids.append(len(fields))
            fields.append(s.pack("<III", k, labels.index(label), v))
        off = 0 if not ids else ids[0] if len(ids) == 1 else len(idx)
        if len(ids) > 1:
            idx.extend(s.pack("<" + "I" * len(ids), *ids))
        nodes[ni] = s.pack("<III", n[0], off, len(ids))
        return ni

    node(root)
    blocks = [
        b"".join(nodes),
        b"".join(fields),
        b"".join(x.encode().ljust(16, b"\0") for x in labels),
        bytes(data),
        bytes(idx),
        bytes(lists),
    ]
    sizes = [12, 12, 16, 1, 1, 1]
    header = []
    offset = 56
    for b, size in zip(blocks, sizes):
        header.extend((offset, len(b) // size))
        offset += len(b)
    return signature + s.pack("<12I", *header) + b"".join(blocks)


def text(value):
    return (
        s.pack("<II", 0xFFFFFFFF, 1)
        + s.pack("<II", 0, len(value.encode()))
        + value.encode()
    )
