"""Merge demo history from a private backup; retain new messages and authored data.

Call with the companion stopped and a current backup already taken. This never
restores quest flags, profiles, settings or lore. No message content is printed.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

DEMO_NPCS = (
    "rq_guard",
    "rq_wizard",
    "rq_cleric",
    "rq_holt",
    "rq_king",
    "tavern_owner",
    "merchant_one",
)


def restore(database, backup):
    if Path(database).resolve() == Path(backup).resolve():
        raise ValueError("Separate live and backup databases required")
    with closing(
        sqlite3.connect(Path(backup).resolve().as_uri() + "?mode=ro", uri=True)
    ) as old:
        with closing(sqlite3.connect(database)) as live, live:
            counts = {}
            for table, fields in (
                ("messages", ("npc", "player", "speaker", "text", "created")),
                ("memories", ("npc", "player", "text", "created")),
            ):
                names = ",".join(fields)
                rows = old.execute(
                    f"SELECT id,{names} FROM {table} WHERE npc IN ({','.join('?' for _ in DEMO_NPCS)}) ORDER BY id",
                    DEMO_NPCS,
                ).fetchall()
                high = max(
                    [
                        live.execute(
                            f"SELECT COALESCE(MAX(id),0) FROM {table}"
                        ).fetchone()[0]
                    ]
                    + [r[0] for r in rows]
                )
                count = 0
                for ident, *values in rows:
                    match = " AND ".join(name + " IS ?" for name in fields)
                    if live.execute(
                        f"SELECT 1 FROM {table} WHERE {match}", values
                    ).fetchone():
                        continue
                    if live.execute(
                        f"SELECT 1 FROM {table} WHERE id=?", (ident,)
                    ).fetchone():
                        # Freed IDs may have been reused since the reset. Move the
                        # newer row above the old range instead of overwriting it.
                        high += 1
                        live.execute(
                            f"UPDATE {table} SET id=? WHERE id=?", (high, ident)
                        )
                    live.execute(
                        f"INSERT INTO {table} (id,{names}) VALUES ({','.join('?' for _ in range(len(fields)+1))})",
                        (ident, *values),
                    )
                    count += 1
                counts[table] = count
            return counts
