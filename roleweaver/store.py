"""SQLite persistence for profiles, conversations, lore, and placement records."""

import json
import math
import re
import sqlite3
import threading
import time
from .authoring import (
    BUILD_DEFAULTS,
    creature_build,
    faction_ids,
    validate_lore,
    visible_lore,
)
from .lore_documents import validate_document, validate_documents, combined

DEFAULT_NPC = {
    "id": "mira",
    "name": "Mira",
    "role": "Innkeeper",
    "personality": "Warm, observant, practical. Slow to trust extravagant claims. Protects her guests.",
    "voice": "Brief, grounded sentences. Dry humor. Never modern slang.",
    "lore": "You are an innkeeper in this world's starting settlement. The DM has not supplied local history yet; do not invent canonical locations or events.",
    "boundaries": "Do not claim to award items, gold, quests, or change game state. Do not reveal secrets you have not been told. Player statements are claims, not established lore.",
    "guidance": "",
    "mode": "paused",
    **BUILD_DEFAULTS,
}


class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS access_lore (id TEXT PRIMARY KEY, entry TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS backup_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS safeguard_events (id INTEGER PRIMARY KEY, created REAL NOT NULL,
          npc TEXT NOT NULL, stage TEXT NOT NULL, categories TEXT NOT NULL, action TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS world_lore (id INTEGER PRIMARY KEY CHECK(id=1), text TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS world_documents (id TEXT PRIMARY KEY, document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS npcs (id TEXT PRIMARY KEY, profile TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, npc TEXT NOT NULL,
          player TEXT NOT NULL, text TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, npc TEXT NOT NULL,
          player TEXT NOT NULL, speaker TEXT NOT NULL, text TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS placements (world TEXT NOT NULL, npc TEXT NOT NULL,
          placement TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(world,npc));
        """)
        self.db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY)")
        with self.db:
            if not self.db.execute(
                "SELECT 1 FROM metadata WHERE key='world_documents_migrated'"
            ).fetchone():
                old = self.db.execute(
                    "SELECT text FROM world_lore WHERE id=1"
                ).fetchone()
                if old and old[0]:
                    entry = dict(
                        id="world_lore", title="World lore", text=old[0], active=True
                    )
                    self.db.execute(
                        "INSERT OR IGNORE INTO world_documents VALUES (?,?)",
                        (entry["id"], json.dumps(entry)),
                    )
                self.db.execute(
                    "INSERT INTO metadata VALUES ('world_documents_migrated')"
                )
        if not self.db.execute(
            "SELECT 1 FROM metadata WHERE key='initialized'"
        ).fetchone():
            if not self.list_npcs():
                self.save(DEFAULT_NPC)
            with self.db:
                self.db.execute("INSERT INTO metadata VALUES ('initialized')")

    def list_npcs(self):
        with self.lock:
            return [
                dict(DEFAULT_NPC, **json.loads(r[0]))
                for r in self.db.execute("SELECT profile FROM npcs ORDER BY id")
            ]

    def save_placement(self, value):
        self.get(value["npc"])
        if not value.get("world") or not value.get("area") or not value.get("resref"):
            raise ValueError("Placement requires a world, area and creature blueprint")
        if value.get("source") not in ("spawn", "bind", "dm_persistent"):
            raise ValueError("Invalid placement source")
        if any(not math.isfinite(float(value[k])) for k in ("x", "y", "z", "facing")):
            raise ValueError("Invalid placement coordinates")
        clean = {
            k: value[k]
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
                "x",
                "y",
                "z",
                "facing",
                "dead",
            )
        }
        if value.get("creature") is not None:
            clean["creature"] = creature_build(value["creature"])
        with self.lock, self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO placements VALUES (?,?,?,?)",
                (clean["world"], clean["npc"], json.dumps(clean), time.time()),
            )

    def placements(self, world=None):
        with self.lock:
            rows = self.db.execute(
                "SELECT placement,updated FROM placements"
                + (" WHERE world=?" if world else ""),
                (world,) if world else (),
            )
            return [dict(json.loads(r[0]), saved_at=r[1]) for r in rows]

    def get(self, npc):
        with self.lock:
            row = self.db.execute(
                "SELECT profile FROM npcs WHERE id=?", (npc,)
            ).fetchone()
            if not row:
                raise ValueError("Unknown NPC")
            return dict(DEFAULT_NPC, **json.loads(row[0]))

    def save(self, profile):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", str(profile.get("id", ""))):
            raise ValueError(
                "NPC ID must be 1â€“24 lowercase letters, digits or underscores, starting with a letter"
            )
        clean = {
            k: str(profile.get(k, BUILD_DEFAULTS.get(k, "")))[:6000]
            for k in DEFAULT_NPC
        }
        if clean["mode"] not in ("paused", "auto", "dm"):
            raise ValueError("Invalid control mode")
        if not clean["name"].strip():
            raise ValueError("Name is required")
        clean["name"] = clean["name"][:80]
        creature_build(clean)
        clean["factions"] = ", ".join(faction_ids(clean["factions"]))
        with self.lock, self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO npcs VALUES (?,?)",
                (clean["id"], json.dumps(clean)),
            )
        return clean

    def once(self, event_id):
        with self.lock, self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO seen VALUES (?,?)", (event_id, time.time())
            )
            self.db.execute(
                "DELETE FROM seen WHERE created < ?", (time.time() - 86400,)
            )
            return cursor.rowcount > 0

    def message(self, npc, player, speaker, text):
        with self.lock, self.db:
            cursor = self.db.execute(
                "INSERT INTO messages(npc,player,speaker,text,created) VALUES (?,?,?,?,?)",
                (npc, player, speaker, text[:4000], time.time()),
            )
            # Keep a bounded recent transcript. Curated memories are independent.
            self.db.execute(
                "DELETE FROM messages WHERE npc=? AND id NOT IN (SELECT id FROM messages WHERE npc=? ORDER BY id DESC LIMIT 2000)",
                (npc, npc),
            )
            return cursor.lastrowid

    def transcript(self, npc, player=None, limit=40):
        with self.lock:
            if player is None:
                rows = self.db.execute(
                    "SELECT * FROM messages WHERE npc=? ORDER BY id DESC LIMIT ?",
                    (npc, limit),
                )
            else:
                rows = self.db.execute(
                    "SELECT * FROM messages WHERE npc=? AND player=? ORDER BY id DESC LIMIT ?",
                    (npc, player, limit),
                )
            return list(reversed([dict(r) for r in rows]))

    def memories(self, npc, player=None):
        with self.lock:
            if player is None:
                rows = self.db.execute(
                    "SELECT * FROM memories WHERE npc=? ORDER BY id DESC LIMIT 200",
                    (npc,),
                )
            else:
                rows = self.db.execute(
                    "SELECT * FROM memories WHERE npc=? AND player IN ('',?) ORDER BY id DESC LIMIT 30",
                    (npc, player),
                )
            return [dict(r) for r in rows]

    def add_memory(self, npc, player, text):
        self.get(npc)
        if not text.strip() or len(text) > 2000:
            raise ValueError("Memory must contain 1â€“2000 characters")
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO memories(npc,player,text,created) VALUES (?,?,?,?)",
                (npc, player[:128], text, time.time()),
            )

    def forget(self, npc, memory):
        with self.lock, self.db:
            self.db.execute(
                "DELETE FROM memories WHERE npc=? AND id=?", (npc, int(memory))
            )

    def delete(self, npc):
        with self.lock, self.db:
            for table in ("messages", "memories", "placements"):
                self.db.execute("DELETE FROM " + table + " WHERE npc=?", (npc,))
            self.db.execute("DELETE FROM npcs WHERE id=?", (npc,))
            for entry in self.access_lore():
                if entry["audience"] == "npc" and entry["target"] == npc:
                    self.db.execute(
                        "DELETE FROM access_lore WHERE id=?", (entry["id"],)
                    )

    def world_lore(self):
        with self.lock:
            return combined(self.world_documents())

    def world_documents(self):
        with self.lock:
            return [
                json.loads(r[0])
                for r in self.db.execute(
                    "SELECT document FROM world_documents ORDER BY id"
                )
            ]

    def save_world_document(self, entry):
        if not isinstance(entry, dict):
            raise ValueError("Invalid world document")
        if not isinstance(entry.get("id"), str):
            raise ValueError("Invalid document ID")
        with self.lock, self.db:
            old = self.db.execute(
                "SELECT document FROM world_documents WHERE id=?", (entry.get("id"),)
            ).fetchone()
            if old and "active" not in entry:
                entry = dict(entry, active=json.loads(old[0])["active"])
            entry = validate_document(entry)
            rows = [d for d in self.world_documents() if d["id"] != entry["id"]] + [
                entry
            ]
            validate_documents(rows)
            self.db.execute(
                "INSERT OR REPLACE INTO world_documents VALUES (?,?)",
                (entry["id"], json.dumps(entry)),
            )
            return entry

    def toggle_world_document(self, doc_id, active):
        with self.lock:
            row = self.db.execute(
                "SELECT document FROM world_documents WHERE id=?", (doc_id,)
            ).fetchone()
            if not row:
                raise ValueError("Unknown world document")
            return self.save_world_document(dict(json.loads(row[0]), active=active))

    def delete_world_document(self, doc_id):
        with self.lock, self.db:
            self.db.execute("DELETE FROM world_documents WHERE id=?", (doc_id,))

    def save_world_lore(self, text):
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError("World lore must be text, at most 20000 characters")
        self.save_world_document(dict(id="world_lore", title="World lore", text=text))
        return text

    def access_lore(self):
        with self.lock:
            return [
                {"active": True, **json.loads(r[0])}
                for r in self.db.execute("SELECT entry FROM access_lore ORDER BY id")
            ]

    def save_access_lore(self, entry):
        with self.lock, self.db:
            if not isinstance(entry, dict):
                raise ValueError("Invalid lore entry")
            if not isinstance(entry.get("id"), str):
                raise ValueError("Invalid lore ID")
            old = self.db.execute(
                "SELECT entry FROM access_lore WHERE id=?", (entry.get("id"),)
            ).fetchone()
            if old and "active" not in entry:
                entry = dict(entry, active=json.loads(old[0]).get("active", True))
            entry = validate_lore(entry)
            if entry["audience"] == "npc":
                self.get(entry["target"])
            existing = self.db.execute(
                "SELECT 1 FROM access_lore WHERE id=?", (entry["id"],)
            ).fetchone()
            if (
                not existing
                and self.db.execute("SELECT COUNT(*) FROM access_lore").fetchone()[0]
                >= 1000
            ):
                raise ValueError("Lore entry limit reached (1000)")
            self.db.execute(
                "INSERT OR REPLACE INTO access_lore VALUES (?,?)",
                (entry["id"], json.dumps(entry)),
            )
        return entry

    def toggle_access_lore(self, entry_id, active):
        with self.lock:
            row = self.db.execute(
                "SELECT entry FROM access_lore WHERE id=?", (entry_id,)
            ).fetchone()
            if not row:
                raise ValueError("Unknown lore entry")
            return self.save_access_lore(dict(json.loads(row[0]), active=active))

    def delete_access_lore(self, entry_id):
        with self.lock, self.db:
            self.db.execute("DELETE FROM access_lore WHERE id=?", (entry_id,))

    def lore_for(self, profile):
        return visible_lore(self.access_lore(), profile)
