"""Clean an existing stopped demo using its authored content as an allowlist.

Preview is the default. --apply requires the add-on to be stopped and creates a
private recovery folder before changing anything. Never run this on a production
world: unlisted NPCs, lore and encounter records are deliberately removed.
Kept NPCs retain their memories and conversation context. The dashboard starts a
new activity view; translations, language preferences and provider settings stay.
"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from roleweaver import actions, encounters, merchants
from roleweaver.store import Store
from demo.encounter_content import armed_run


def prune(store, content, world, now=None):
    """Caller owns the stopped instance and its backup; mutations are atomic."""
    now = time.time() if now is None else now
    keep = {n["id"] for n in content["npcs"]}
    actual = {n["id"] for n in store.list_npcs()}
    if not keep or keep - actual:
        raise ValueError(
            "Import the demo content before cleaning; required profiles are missing"
        )
    if any(p["world"] != world for p in store.placements()):
        raise ValueError(
            "Cleanup requires a database containing only the selected demo world"
        )

    def setting(key, default):
        row = store.db.execute(
            "SELECT value FROM backup_settings WHERE key=?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else default

    config = actions.settings(setting("controlled_actions", None))
    config["npcs"] = {k: v for k, v in config["npcs"].items() if k in keep}
    for policy in config["npcs"].values():
        policy["npc_combat"]["targets"] = [
            k for k in policy["npc_combat"]["targets"] if k in keep
        ]
        patrol = policy.get("patrol", {})
        if patrol:
            patrol["checkins"] = {
                k: v for k, v in patrol["checkins"].items() if v in keep
            }
    old = encounters.settings(setting("encounters", None))
    definitions = {}
    for raw in content.get("encounters", []):
        definition = encounters.definition(old["templates"].get(raw["id"], raw))
        if any(a["npc"] not in keep for a in definition["actors"]):
            raise ValueError("Kept encounter refers to an NPC outside the demo cast")
        definitions[definition["id"]] = definition
    used = {d["location"] for d in definitions.values() if d["location"]}
    for p in config["npcs"].values():
        used.update(
            p["destinations"]
            + p["lead_destinations"]
            + p.get("patrol", {}).get("route", [])
        )
        if p["home"]:
            used.add(p["home"])
    config["destinations"] = {
        k: v for k, v in config["destinations"].items() if k in used
    }
    config = actions.settings(config)
    if used - config["destinations"].keys():
        raise ValueError("A required demo destination is missing")
    scenes = encounters.settings(
        dict(
            templates=definitions,
            runs={
                k: armed_run(d, world)
                for k, d in definitions.items()
                if d["automation"]["enabled"]
            },
        )
    )
    shop = merchants.configs(
        {k: v for k, v in setting("merchant_configs", {}).items() if k in keep}
    )
    allowed_lore = {d["id"] for d in content.get("access_lore", [])}
    allowed_docs = {d["id"] for d in content.get("world_documents", [])}
    removed = sorted(actual - keep)
    report = dict(
        kept_npcs=sorted(keep),
        removed_npcs=removed,
        encounters=sorted(definitions),
        destinations=len(config["destinations"]),
        removed_lore=[
            e["id"] for e in store.access_lore() if e["id"] not in allowed_lore
        ],
        removed_documents=[
            e["id"] for e in store.world_documents() if e["id"] not in allowed_docs
        ],
    )
    with store.lock, store.db:
        for npc in removed:
            for table in ("messages", "memories", "placements", "story_visits", "npcs"):
                column = "id" if table == "npcs" else "npc"
                store.db.execute(f"DELETE FROM {table} WHERE {column}=?", (npc,))
        for table, entries in (
            ("access_lore", report["removed_lore"]),
            ("world_documents", report["removed_documents"]),
        ):
            store.db.executemany(
                f"DELETE FROM {table} WHERE id=?", [(k,) for k in entries]
            )
        store.db.execute("DELETE FROM safeguard_events")
        for key, value in dict(
            controlled_actions=config,
            encounters=scenes,
            merchant_configs=shop,
            live_encounter_journal={},
            checkin_last={},
            payment_offers={},
            payment_receipts=[],
            control_sessions={
                k: v for k, v in setting("control_sessions", {}).items() if k in keep
            },
            dashboard_history_since=now,
        ).items():
            store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                (key, json.dumps(value)),
            )
    return report


def clean(directory, content, world, apply=False):
    """Take the same OS lock as the add-on before working on the demo database."""
    from roleweaver.recovery_runtime import InstanceLock

    directory = Path(directory).resolve()
    database = directory / "roleweaver.sqlite3"
    if not database.is_file():
        raise ValueError("No existing demo database in this data folder")
    with InstanceLock(directory):
        if not apply:
            source = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
            store = Store(":memory:")
            try:
                source.backup(store.db)
                return prune(store, content, world)
            finally:
                source.close()
                store.db.close()
        backup = directory.parent / ("before-demo-cleanup-" + str(time.time_ns()))
        backup.mkdir(mode=0o700)
        for path in directory.glob("*.sqlite3"):
            with (
                closing(sqlite3.connect(path)) as src,
                closing(sqlite3.connect(backup / path.name)) as dst,
            ):
                src.backup(dst)
        for name in ("identity_salt",):
            if (directory / name).is_file():
                shutil.copy2(directory / name, backup / name)
        logs = directory / "logs"
        if logs.exists():
            shutil.copytree(logs, backup / "logs")
        store = Store(database)
        try:
            report = prune(store, content, world)
            if store.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError(
                    "Database integrity check failed; preserve the recovery copy"
                )
        finally:
            store.db.close()
        usage = directory / "usage.sqlite3"
        if usage.is_file():
            with closing(sqlite3.connect(usage)) as db, db:
                db.execute("DELETE FROM requests")
        # Archived support logs remain in the private backup, outside dashboard reads.
        for path in logs.glob("errors*.jsonl"):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        report["backup"] = str(backup)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--content", default=ROOT / "demo/content.json", type=Path)
    parser.add_argument("--world-id", default="rw_demo")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            clean(
                args.data_dir,
                json.loads(args.content.read_text(encoding="utf-8")),
                args.world_id,
                args.apply,
            ),
            indent=2,
        )
    )
