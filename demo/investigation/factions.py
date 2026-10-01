"""Demo faction table: neutral civilians and isolated encounter casts.

The first five IDs preserve NWN's standard factions. Extra factions are local,
so attacking a troll does not lower reputation with the town or its captive.
This table is for the stock demo, never injected into an owner's existing world.
"""

from collections import OrderedDict
from tools.gff import write


def build():
    names = [
        "Player",
        "Hostile",
        "Commoner",
        "Merchant",
        "Defender",
        "RW Trolls",
        "RW Captive",
        "RW Robber",
    ]
    standard = [
        [100, 0, 50, 50, 50],
        [0, 100, 0, 0, 0],
        [50, 0, 100, 50, 100],
        [50, 0, 50, 100, 100],
        [50, 0, 50, 100, 100],
    ]
    factions = [
        (
            0,
            OrderedDict(
                FactionName=(10, n.encode()),
                FactionParentID=(4, 0xFFFFFFFF),
                FactionGlobal=(2, int(i < 5)),
            ),
        )
        for i, n in enumerate(names)
    ]
    reputations = []
    for i in range(len(names)):
        for j in range(len(names)):
            score = standard[i][j] if i < 5 and j < 5 else (100 if i == j else 50)
            reputations.append(
                (
                    1,
                    OrderedDict(
                        FactionID1=(4, i), FactionID2=(4, j), FactionRep=(4, score)
                    ),
                )
            )
    return write(
        b"FAC V3.2",
        (
            0xFFFFFFFF,
            OrderedDict(FactionList=(15, factions), RepList=(15, reputations)),
        ),
    )
