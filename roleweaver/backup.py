"""Portable, validated data-only backups. No configuration or credentials."""

import json
import math
import re
import time
import secrets
from .store import DEFAULT_NPC
from .authoring import BUILD_DEFAULTS, creature_build, faction_ids, validate_lore
from . import safeguards, conversation, actions, merchants
from .lore_documents import validate_documents, combined

LIMIT = 32 * 1024 * 1024


def validate(data):
    if (
        not isinstance(data, dict)
        or data.get("format") != "roleweaver-backup"
        or data.get("version") not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
    ):
        raise ValueError("Unsupported Role Weaver backup")

    def text(value, limit):
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("Invalid or oversized backup text")
        return value

    salt = text(data.get("identity_salt"), 64)
    if not re.fullmatch(r"[0-9a-f]{64}", salt):
        raise ValueError("Invalid player identity salt")
    lore = text(data.get("world_lore"), 20000)
    profiles = data.get("npcs")
    if not isinstance(profiles, list) or len(profiles) > 1000:
        raise ValueError("Invalid NPC list")
    ids, clean = set(), []
    for p in profiles:
        if not isinstance(p, dict):
            raise ValueError("Invalid profile")
        q = {k: text(p.get(k, BUILD_DEFAULTS.get(k, "")), 6000) for k in DEFAULT_NPC}
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", q["id"])
            or q["id"] in ids
            or not q["name"].strip()
            or len(q["name"]) > 80
        ):
            raise ValueError("Invalid or duplicate NPC identity")
        creature_build(q)
        faction_ids(q["factions"])
        q["mode"] = "paused"
        ids.add(q["id"])
        clean.append(q)
    result = dict(
        format="roleweaver-backup",
        version=1,
        identity_salt=salt,
        world_lore=lore,
        npcs=clean,
    )
    if data["version"] >= 5 and "world_documents" not in data:
        raise ValueError("Missing world documents")
    result["world_documents"] = validate_documents(
        data.get(
            "world_documents",
            (
                [dict(id="world_lore", title="World lore", text=lore, active=True)]
                if lore
                else []
            ),
        )
    )
    result["world_lore"] = combined(result["world_documents"])
    if data["version"] >= 6 and "conversation" not in data:
        raise ValueError("Missing conversation settings")
    if "conversation" in data:
        if not isinstance(data["conversation"], dict):
            raise ValueError("Invalid conversation settings")
        result["conversation"] = (
            conversation.settings if data["version"] >= 8 else conversation.migrate
        )(data["conversation"])
    if data["version"] >= 7 and "controlled_actions" not in data:
        raise ValueError("Missing controlled actions")
    if "controlled_actions" in data:
        if not isinstance(data["controlled_actions"], dict):
            raise ValueError("Invalid controlled actions")
        result["controlled_actions"] = actions.settings(data["controlled_actions"])
        if not set(result["controlled_actions"]["npcs"]).issubset(ids):
            raise ValueError("Action permissions reference unknown NPC")
    if data["version"] >= 10 and "merchant_configs" not in data:
        raise ValueError("Missing merchant settings")
    result["merchant_configs"] = merchants.configs(data.get("merchant_configs"))
    if not set(result["merchant_configs"]).issubset(ids):
        raise ValueError("Merchant settings reference unknown NPC")
    if "safeguards" in data:
        if not isinstance(data["safeguards"], dict):
            raise ValueError("Invalid safeguard settings in backup")
        result["safeguards"] = safeguards.settings(data["safeguards"])
    entries = data.get("access_lore", [])
    if not isinstance(entries, list) or len(entries) > 1000:
        raise ValueError("Invalid lore entries")
    result["access_lore"] = [validate_lore(e) for e in entries]
    if len({e["id"] for e in result["access_lore"]}) != len(entries):
        raise ValueError("Duplicate lore IDs")
    for table, maximum in (("messages", 200000), ("memories", 200000)):
        rows = data.get(table)
        if not isinstance(rows, list) or len(rows) > maximum:
            raise ValueError("Invalid history list")
        result[table] = []
        for r in rows:
            if not isinstance(r, dict) or r.get("npc") not in ids:
                raise ValueError("History references unknown NPC")
            created = r.get("created")
            if not isinstance(created, (int, float)) or not math.isfinite(created):
                raise ValueError("Invalid history date")
            q = dict(
                npc=r["npc"],
                player=text(r.get("player"), 128),
                text=text(r.get("text"), 4000 if table == "messages" else 2000),
                created=created,
            )
            if table == "messages":
                if r.get("speaker") not in ("npc", "player"):
                    raise ValueError("Invalid speaker")
                q["speaker"] = r["speaker"]
            result[table].append(q)
    placements = (
        data.get("placements", []) if data["version"] == 1 else data.get("placements")
    )
    if not isinstance(placements, list) or len(placements) > 10000:
        raise ValueError("Invalid saved NPC placements")
    result["placements"] = []
    keys = set()
    for r in placements:
        if not isinstance(r, dict) or r.get("npc") not in ids:
            raise ValueError("Placement references unknown NPC")
        q = {
            k: text(r.get(k), 256)
            for k in (
                "npc",
                "world",
                "session",
                "area",
                "area_tag",
                "tag",
                "resref",
                "name",
                "source",
            )
        }
        if (
            not q["world"]
            or not q["area"]
            or not re.fullmatch(r"[a-zA-Z0-9_]{1,16}", q["resref"])
        ):
            raise ValueError("Invalid placement world, area or blueprint")
        if q["source"] not in ("spawn", "bind", "dm_persistent"):
            raise ValueError("Invalid placement type")
        if (q["world"], q["npc"]) in keys:
            raise ValueError("Duplicate placement")
        keys.add((q["world"], q["npc"]))
        for k in ("x", "y", "z", "facing"):
            v = r.get(k)
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError("Invalid placement coordinates")
            q[k] = v
        if r.get("dead") not in (0, 1):
            raise ValueError("Invalid creature life state")
        q["dead"] = r["dead"]
        if r.get("creature") is not None:
            q["creature"] = creature_build(r["creature"])
        result["placements"].append(q)
    return result


def export(store, salt):
    with store.lock:
        policy = store.db.execute(
            "SELECT value FROM backup_settings WHERE key='safeguards'"
        ).fetchone()
        action_row = store.db.execute(
            "SELECT value FROM backup_settings WHERE key='controlled_actions'"
        ).fetchone()
        talk = store.db.execute(
            "SELECT value FROM backup_settings WHERE key='conversation'"
        ).fetchone()
        merchant_row = store.db.execute(
            "SELECT value FROM backup_settings WHERE key='merchant_configs'"
        ).fetchone()
        return dict(
            format="roleweaver-backup",
            version=11,
            merchant_configs=merchants.configs(
                json.loads(merchant_row[0]) if merchant_row else None
            ),
            controlled_actions=actions.settings(
                json.loads(action_row[0]) if action_row else None
            ),
            conversation=conversation.migrate(json.loads(talk[0]) if talk else None),
            world_documents=store.world_documents(),
            safeguards=safeguards.settings(json.loads(policy[0]) if policy else None),
            access_lore=store.access_lore(),
            placements=store.placements(),
            created=time.time(),
            identity_salt=salt,
            npcs=store.list_npcs(),
            world_lore=store.world_lore(),
            **{
                t: [
                    dict(r)
                    for r in store.db.execute("SELECT * FROM " + t + " ORDER BY id")
                ]
                for t in ("messages", "memories")
            },
        )


def replace(store, data):
    with store.lock, store.db:
        configs = {
            p["id"]: dict(
                rules=data.get("merchant_configs", {})
                .get(p["id"], {})
                .get("rules", dict(merchants.DEFAULT_RULES)),
                revision=secrets.token_hex(12),
            )
            for p in data["npcs"]
        }
        store.db.execute(
            "INSERT OR REPLACE INTO backup_settings VALUES ('merchant_configs',?)",
            (json.dumps(configs),),
        )
        store.db.execute(
            "INSERT OR REPLACE INTO backup_settings VALUES ('controlled_actions',?)",
            (json.dumps(actions.settings(data.get("controlled_actions"))),),
        )
        if "conversation" in data:
            store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES ('conversation',?)",
                (json.dumps(conversation.settings(data["conversation"])),),
            )
        if "safeguards" in data:
            store.db.execute(
                "INSERT OR REPLACE INTO backup_settings VALUES ('safeguards',?)",
                (json.dumps(safeguards.settings(data["safeguards"])),),
            )
        for table in (
            "npcs",
            "messages",
            "memories",
            "world_lore",
            "world_documents",
            "placements",
            "seen",
            "access_lore",
        ):
            store.db.execute("DELETE FROM " + table)
        for entry in data.get("access_lore", []):
            store.db.execute(
                "INSERT INTO access_lore VALUES (?,?)", (entry["id"], json.dumps(entry))
            )
        for p in data["npcs"]:
            store.db.execute("INSERT INTO npcs VALUES (?,?)", (p["id"], json.dumps(p)))
        store.db.execute("INSERT INTO world_lore VALUES (1,?)", (data["world_lore"],))
        for entry in data.get("world_documents", []):
            store.db.execute(
                "INSERT INTO world_documents VALUES (?,?)",
                (entry["id"], json.dumps(entry)),
            )
        for table in ("messages", "memories"):
            columns = (
                ("npc", "player", "text", "created", "speaker")
                if table == "messages"
                else ("npc", "player", "text", "created")
            )
            store.db.executemany(
                "INSERT INTO "
                + table
                + " ("
                + ",".join(columns)
                + ") VALUES ("
                + ",".join("?" for _ in columns)
                + ")",
                [tuple(r[k] for k in columns) for r in data[table]],
            )
        for p in data.get("placements", []):
            store.db.execute(
                "INSERT INTO placements VALUES (?,?,?,?)",
                (p["world"], p["npc"], json.dumps(p), time.time()),
            )
        store.db.execute(
            "INSERT OR REPLACE INTO backup_settings VALUES ('identity_salt',?)",
            (data["identity_salt"],),
        )

        store.db.execute(
            "INSERT OR REPLACE INTO backup_settings VALUES ('placement_restore_hold',?)",
            (json.dumps(data.get("restore_hold", {})),),
        )
