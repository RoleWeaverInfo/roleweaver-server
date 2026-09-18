"""Profile lifecycle, game placement, and DM control.

Mixin methods run on Service and share its lock, store, state, and command queue.
They do not own separate worker pools or database connections.
"""

import json
import secrets
import time
from ..authoring import creature_build, BUILD_DEFAULTS


class NPCService:
    """Profile lifecycle, game placement, and DM control."""

    def control(self, npc, mode):
        if mode not in ("auto", "paused", "dm"):
            raise ValueError("Invalid control mode")
        with self.lock:
            self.generations[npc] = self.generations.get(npc, 0) + 1
            return self.command(npc, "mode", mode=mode)

    def save_profile(self, profile):
        with self.lock:
            npc = profile["id"]
            self.generations[npc] = self.generations.get(npc, 0) + 1
            try:
                profile["mode"] = self.store.get(npc)["mode"]
            except ValueError:
                profile["mode"] = "paused"
            return self.store.save(profile)

    def finish_delete(self, npc):
        self.action_config["npcs"].pop(npc, None)
        self.persist_actions()
        self.action_jobs.pop(npc, None)
        self.generations[npc] = self.generations.get(npc, 0) + 1
        self.store.delete(npc)
        self.states.pop(npc, None)
        self.pending = {k: v for k, v in self.pending.items() if v["npc"] != npc}

    def delete_npc(self, npc):
        with self.lock:
            self.store.get(npc)
            self.generations[npc] = self.generations.get(npc, 0) + 1
            if npc in self.states:
                request = self.command(npc, "delete")
                return {"pending": True, "request": request}
            self.finish_delete(npc)
            return {"pending": False}

    def spawn_at_dm(self, npc, dm, blueprint, persistence="temporary"):
        with self.lock:
            if self.restoring or not self.config.get("allow_dm_spawn", False):
                raise ValueError("DM spawning is disabled")
            if persistence not in ("temporary", "persistent"):
                raise ValueError("Choose temporary or persistent")
            if persistence == "persistent" and not self.config.get(
                "allow_persistent_spawn"
            ):
                raise ValueError("Persistent spawning is disabled")
            if persistence not in ("temporary", "persistent"):
                raise ValueError("Choose temporary or persistent")
            if persistence == "persistent" and not self.config.get(
                "allow_persistent_spawn"
            ):
                raise ValueError("Persistent spawning is disabled")
            profile = self.store.get(npc)
            if blueprint not in ("innkeeper", "rw_custom"):
                raise ValueError("Blueprint is not allowed by this test world")
            if npc in self.states and time.monotonic() - self.states[npc]["seen"] < 4:
                raise ValueError("This profile already has a connected creature")
            if any(
                v["npc"] == npc and v["kind"] == "spawn_dm"
                for v in self.pending.values()
            ):
                raise ValueError("A spawn request is already pending")
            target = self.dms.get(dm)
            if not target or time.monotonic() - target["seen"] >= 3:
                raise ValueError(
                    "DM is no longer available; release possession and refresh"
                )
            request = secrets.token_hex(12)
            command = dict(
                kind="spawn_dm",
                npc=npc,
                dm=dm,
                token=target["token"],
                session=target["session"],
                expires=target["tick"] + 5,
                request=request,
                blueprint=blueprint,
                name=profile["name"],
                persistence=persistence,
            )
            if blueprint == "rw_custom":
                command["creature"] = creature_build(profile)
            if blueprint == "rw_custom":
                command["creature"] = creature_build(profile)
            self.pending[request] = dict(
                npc=npc, kind="spawn_dm", persistence=persistence, time=time.monotonic()
            )
            try:
                self.redis.call("RPUSH", self.prefix + ":commands", json.dumps(command))
                self.redis.call("EXPIRE", self.prefix + ":commands", 10)
            except Exception:
                self.pending.pop(request, None)
                raise
            return request

    def npc_diagnostic(self, npc):
        s = self.states.get(npc, {})
        d = dict(self.diagnostics.get(npc, {}))
        if not self.redis_ok:
            status = "Redis disconnected"
        elif not s or time.monotonic() - s["seen"] >= 4:
            status = "Creature not connected or not currently spawned"
        elif s.get("dead"):
            status = "Creature is dead"
        elif s.get("possessed") or s["mode"] == "dm":
            status = "DM control or reservation; AI is silent"
        elif s["mode"] == "paused":
            status = "AI paused"
        elif d.get("error"):
            status = d["error"]
        elif npc in self.busy:
            status = "Preparing a reply"
        elif s.get("nearby_players") == 0:
            status = "No eligible player within 10 metres and line of sight"
        else:
            status = "Ready for player Talk; use Name: to address this NPC"
        d["status"] = status
        d["heartbeat_age"] = round(time.monotonic() - s["seen"], 1) if s else None
        return d

    def manage_npc(self, npc, action, dm=None, persistence=None, return_mode=None):
        with self.lock:
            if self.restoring or not self.config.get("allow_dm_spawn"):
                raise ValueError("NPC management is disabled")
            self.store.get(npc)
            state = self.states.get(npc)
            if not state or time.monotonic() - state["seen"] >= 3:
                raise ValueError("Creature is not connected")
            if state.get("source") not in ("dm_temporary", "dm_persistent"):
                raise ValueError("World-managed creatures are protected")
            if state.get("possessed"):
                raise ValueError("Release DM possession first")
            if any(v["npc"] == npc for v in self.pending.values()):
                raise ValueError("Wait for the current command to finish")
            fields = {}
            if action == "move_dm":
                target = self.dms.get(dm)
                if (
                    not target
                    or time.monotonic() - target["seen"] >= 3
                    or target["session"] != state["session"]
                ):
                    raise ValueError("Select an available DM in this world")
                if state.get("dead"):
                    raise ValueError("Cannot move a dead creature")
                fields.update(dm=dm, token=target["token"])
            elif action == "persistence":
                if persistence not in ("temporary", "persistent"):
                    raise ValueError("Choose temporary or persistent")
                if persistence == "persistent" and not self.config.get(
                    "allow_persistent_spawn"
                ):
                    raise ValueError("Persistent spawning is disabled")
                fields["persistence"] = persistence
            elif action == "despawn":
                if return_mode not in ("never", "restart"):
                    raise ValueError("Choose whether the NPC returns after restart")
                if return_mode == "restart" and state["source"] != "dm_persistent":
                    raise ValueError("Only persistent NPCs can return after restart")
                fields["return_mode"] = return_mode
            else:
                raise ValueError("Unknown NPC action")
            if (
                self.placement_restore_hold.get(self.config.get("world_id", ""))
                == state["session"]
            ):
                raise ValueError(
                    "Restart the module to apply restored locations before managing creatures"
                )
            self.generations[npc] = self.generations.get(npc, 0) + 1
            request = self.command(npc, action, **fields)
            self.operations[npc] = dict(
                status="pending", message="Request sent; waiting for game confirmation."
            )
            return request

    def duplicate_profile(self, source, npc, name):
        with self.lock:
            if self.restoring:
                raise ValueError("Wait for restore to finish")
            original = self.store.get(source)
            if (
                any(p["id"] == npc for p in self.store.list_npcs())
                or npc in self.states
            ):
                raise ValueError("Choose a new, unused NPC ID")
            profile = {
                k: original[k]
                for k in (
                    "role",
                    "personality",
                    "voice",
                    "lore",
                    "boundaries",
                    *BUILD_DEFAULTS,
                )
            }
            profile.update(id=npc, name=name, guidance="", mode="paused")
            return self.store.save(profile)

    def set_startup_auto(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("Choose enabled or disabled")
        with self.lock:
            self.startup_auto = enabled
            self.set_setting("startup_auto", enabled)
        return {"startup_auto": enabled}

    def control_all(self, mode):
        if mode not in ("auto", "paused"):
            raise ValueError("Choose Start all or Pause all")
        with self.lock:
            if self.restoring:
                raise ValueError("Wait for backup restore to finish")
            self.suppressed_session = self.world_session if mode == "paused" else ""
            self.set_setting("suppressed_session", self.suppressed_session)
            sent, skipped, failed = [], [], []
            for profile in self.store.list_npcs():
                npc = profile["id"]
                state = self.states.get(npc, {})
                if (
                    not state
                    or time.monotonic() - state["seen"] >= 3
                    or state.get("possessed")
                    or state.get("mode") == "dm"
                    or state.get("dead")
                ):
                    skipped.append(npc)
                    continue
                try:
                    self.control(npc, mode)
                    sent.append(npc)
                except Exception:
                    failed.append(npc)
            return {"sent": sent, "skipped": skipped, "failed": failed, "mode": mode}
