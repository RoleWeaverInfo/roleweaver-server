"""Refresh authored demo content without rebuilding NPCs or moving anything.

Use while the companion is stopped. The CLI first makes a consistent SQLite
backup. Resetting player history is opt-in and affects only the seven demo NPCs;
native quest campaign files must be backed up/reset separately with NWN stopped.
"""

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time

AUTHOR_FIELDS = ("personality", "voice")


def refresh(database, content, reset_player_history=False):
    from roleweaver.store import Store

    value = json.loads(Path(content).read_text(encoding="utf-8"))
    updates = value["profiles"] + value.get("profile_updates", [])
    ids = [row["id"] for row in updates]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate demo profile ID")
    store = Store(database)
    try:
        # Preflight before changing anything. This is a refresh, not a new install.
        existing = {ident: store.get(ident) for ident in ids}
        documents = {d["id"]: d for d in store.world_documents()}
        access = {d["id"]: d for d in store.access_lore()}
        for row in updates:
            profile = existing[row["id"]]
            for key in AUTHOR_FIELDS:
                profile[key] = row[key]
            store.save(profile)
        for row in value["world_documents"]:
            document = dict(row)
            if row["id"] in documents:
                document["active"] = documents[row["id"]]["active"]
            store.save_world_document(document)
        for row in value["access_lore"]:
            document = dict(row)
            if row["id"] in access:
                document["active"] = access[row["id"]]["active"]
            store.save_access_lore(document)
        counts = dict(messages=0, player_memories=0)
        if reset_player_history:
            placeholders = ",".join("?" for _ in ids)
            with store.db:
                counts["messages"] = store.db.execute(
                    f"DELETE FROM messages WHERE npc IN ({placeholders})", ids
                ).rowcount
                counts["player_memories"] = store.db.execute(
                    f"DELETE FROM memories WHERE npc IN ({placeholders}) AND player != ''",
                    ids,
                ).rowcount
        return counts
    finally:
        store.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Companion source directory containing roleweaver/",
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--reset-player-history", action="store_true")
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Existing companion database required")
    sys.path.insert(0, str(args.source))
    backup = args.database.with_name(
        args.database.name + ".before-lore-" + str(time.time_ns())
    )
    # Atomic creation prevents accidentally replacing an older backup.
    with backup.open("xb"):
        pass
    backup.chmod(0o600)
    with sqlite3.connect(args.database) as original, sqlite3.connect(backup) as saved:
        original.backup(saved)
    print("Backup:", backup)
    print(
        "Updated content:",
        refresh(
            args.database,
            Path(__file__).with_name("content.json"),
            args.reset_player_history,
        ),
    )


if __name__ == "__main__":
    main()
