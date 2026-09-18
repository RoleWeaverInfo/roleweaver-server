"""World lore, backup/restore, memory inspection, and conversation settings.

Mixin methods run on Service and share its lock, store, state, and command queue.
They do not own separate worker pools or database connections.
"""

import json
import secrets
import time
from .. import backup, safeguards, conversation
from ..knowledge import inspect_knowledge


class WorldService:
    """World lore, backup/restore, memory inspection, and conversation settings."""

    def save_world_lore(self, text):
        with self.lock:
            saved = self.store.save_world_lore(text)
            for npc in self.states:
                self.generations[npc] = self.generations.get(npc, 0) + 1
            return saved

    def backup_data(self):
        with self.lock:
            return backup.export(self.store, self.salt)

    def restore_data(self, data):
        data = backup.validate(data)
        with self.lock:
            if self.restoring:
                raise ValueError("A restore is already running")
            self.restoring = True
            for npc in self.states:
                self.generations[npc] = self.generations.get(npc, 0) + 1
        try:
            with self.lock:
                requests = [
                    self.command(npc, "mode", mode="paused") for npc in self.states
                ]
            deadline = time.monotonic() + 8
            while True:
                with self.lock:
                    ready = all(r not in self.pending for r in requests) and all(
                        s["mode"] == "paused" and time.monotonic() - s["seen"] < 4
                        for s in self.states.values()
                    )
                if ready:
                    break
                if time.monotonic() > deadline:
                    raise ValueError(
                        "Game did not confirm every NPC paused. No data replaced; retry after checking DM possession and connection."
                    )
                time.sleep(0.1)
            with self.lock:
                # Keep a local recovery copy before replacing any user data.
                recovery = self.directory / (
                    "before-restore-" + str(time.time_ns()) + ".json"
                )
                recovery.write_text(json.dumps(self.backup_data()))
                recovery.chmod(0o600)
                holds = dict(self.placement_restore_hold)
                world = self.config.get("world_id", "")
                sessions = {
                    s["session"]
                    for s in self.states.values()
                    if time.monotonic() - s["seen"] < 4
                }
                if len(sessions) == 1:
                    holds[world] = next(iter(sessions))
                    for placement in data.get("placements", []):
                        if placement["world"] == world:
                            placement["session"] = holds[world]
                data["restore_hold"] = holds
                backup.replace(self.store, data)
                self.safeguard_policy = safeguards.settings(
                    self.setting("safeguards", None)
                )
                self.save_conversation(
                    conversation.migrate(self.setting("conversation", None)), reset=True
                )
                self.init_actions()
                self.set_startup_auto(False)
                self.placement_restore_hold = holds
                self.salt = data["identity_salt"]
                self.pending.clear()
                self.restore_attempts.clear()
                self.last_reply.clear()
            return {"ok": True}
        finally:
            with self.lock:
                self.restoring = False

    def knowledge(self, npc, player=""):
        with self.lock:
            return inspect_knowledge(self.store, npc, player)

    def edit_memory(self, npc, memory, text):
        self.store.get(npc)
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Memory must contain 1-2000 characters")
        with self.store.lock, self.store.db:
            cursor = self.store.db.execute(
                "UPDATE memories SET text=? WHERE npc=? AND id=?",
                (text, npc, int(memory)),
            )
            if not cursor.rowcount:
                raise ValueError("Memory no longer exists for this NPC")
        self.generations[npc] = self.generations.get(npc, 0) + 1
        return {"ok": True}

    def conversation_status(self):
        with self.lock:
            hello = self.conversation_hello
            online = bool(hello) and time.monotonic() - hello.get("seen", 0) < 4
            supported = hello.get("conversation_protocol") == 2
            applied = hello.get(
                "conversation_revision"
            ) == self.conversation_revision and hello.get(
                "conversation"
            ) == conversation.wire(
                self.conversation_policy
            )
            status = (
                "offline"
                if not online
                else (
                    "upgrade_required"
                    if not supported
                    else "applied" if applied else "pending"
                )
            )
            return dict(
                settings=dict(self.conversation_policy),
                status=status,
                applied=hello.get("conversation") if online and supported else None,
            )

    def save_conversation(self, value, reset=False):
        if not isinstance(value, dict):
            raise ValueError("Supply conversation settings as an object")
        policy = conversation.settings(value)
        with self.lock:
            if policy != self.conversation_policy or reset:
                revision = secrets.token_hex(12)
                # Persist both fields in one transaction before publishing to the game.
                with self.store.lock, self.store.db:
                    self.store.db.executemany(
                        "INSERT OR REPLACE INTO backup_settings VALUES (?,?)",
                        [
                            ("conversation", json.dumps(policy)),
                            ("conversation_revision", json.dumps(revision)),
                        ],
                    )
                self.conversation_policy, self.conversation_revision = policy, revision
                self.conversation_sent = 0
                for npc in self.busy:
                    self.generations[npc] = self.generations.get(npc, 0) + 1
            return self.conversation_status()

    def sync_conversation(self, event):
        with self.lock:
            if event.get("world") != self.config.get(
                "world_id", "roleweaver_development"
            ):
                return
            if not isinstance(event.get("session"), str) or not event["session"]:
                return
            if type(event.get("tick")) is not int or event["tick"] < 0:
                return
            previous = self.conversation_hello.get("session")
            self.conversation_hello = dict(event, seen=time.monotonic())
            if previous != event["session"]:
                self.conversation_sent = 0
            if self.restoring or self.conversation_status()["status"] != "pending":
                return
            now = time.monotonic()
            if self.conversation_sent and now - self.conversation_sent < 2:
                return
            command = dict(
                kind="conversation_settings",
                world=event["world"],
                session=event["session"],
                expires=event["tick"] + 5,
                revision=self.conversation_revision,
                settings=conversation.wire(self.conversation_policy),
            )
            self.redis.call("RPUSH", self.prefix + ":commands", json.dumps(command))
            self.conversation_sent = now
