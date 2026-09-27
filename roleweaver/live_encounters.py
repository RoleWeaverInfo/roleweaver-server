"""Temporary DM scenes. Separate journal, API and ownership from persistent encounters.

Previews freeze profile data and game-reported positions. Placement consumes a preview
once. Cleanup uses a game-side ownership token, never a name, tag or proximity search.
The journal survives a companion crash so partial placements can still be cleaned up;
it is not a recipe for respawning scenes after a module restart.
"""

import copy
import json
import math
import re
import secrets
import time

from .authoring import creature_build
from .encounters import definition, reaction, text


class LiveEncounterService:
    def live_combat_choices(self, npc, turn):
        """Only the scene spokesperson may propose combat against this chat's speaker."""
        scene = next(
            (s for s in self.director_scenes().values() if npc in s["actors"]), None
        )
        if not scene or scene["run"]["status"] != "active":
            return [], {}
        run = scene["run"]
        direction = self.director_npc_context(npc)
        if direction.get("holding") or direction.get("finished"):
            return [], {}
        policy = run["template"]["reaction"]
        if (
            policy.get("combat_mode") != "conversation"
            or not policy["attack"]
            or npc != next(iter(scene["actors"]))
            or not turn.get("event_id")
            or self.states.get(npc, {}).get("encounter_protocol", 0) < 3
        ):
            return [], {}
        choices = [
            dict(
                id="encounter:warn",
                label="Deliver the DM's combat warning; do not attack",
            ),
            dict(
                id="encounter:stand_down",
                label="Accept a peaceful resolution and end this activation without combat",
            ),
        ]
        if turn.get("attack_ready") is True:
            choices = [a for a in choices if a["id"] != "encounter:warn"]
            choices.append(
                dict(
                    id="encounter:attack",
                    label="Request combat against the warned speaker because the DM conditions are met",
                )
            )
        return choices, dict(
            encounter=run["template"]["id"],
            token=str(run["started"]),
            **self.scene_authority(scene),
            world=self.config["world_id"],
            combat_event=turn["event_id"],
        )

    def init_live_encounters(self):
        self.live_scenes = self.setting("live_encounter_journal", {})
        self.live_captures = {}
        self.live_previews = {}
        self.live_sync_at = {}
        self.live_hello = {}
        self.live_assistant_busy = False
        self.live_assistant_last = 0
        for scene in self.live_scenes.values():
            if scene["run"]["status"] in ("active", "placing"):
                scene["run"]["status"] = "paused"
                self.encounter_log(
                    scene["run"],
                    "Companion restarted; review or clean up this live scene.",
                )
        self.persist_live()

    def assist_live(self, body):
        from . import dm_assistant, provider

        if (
            not isinstance(body, dict)
            or set(body) != {"instruction", "scene", "allow_combat"}
            or type(body["allow_combat"]) is not bool
        ):
            raise ValueError("Invalid assistant request")
        instruction = text(body["instruction"], 3000, True)
        scene_id = text(body["scene"], 100)
        with self.lock:
            if (
                self.restoring
                or self.live_assistant_busy
                or time.monotonic() - self.live_assistant_last < 5
            ):
                raise ValueError(
                    "Assistant is busy; wait before requesting another proposal"
                )
            profiles = {
                p["id"]: dict(id=p["id"], name=p["name"], creature=p.get("creature"))
                for p in self.store.list_npcs()
                if not p["id"].startswith("live_")
            }
            if len(profiles) > 100:
                raise ValueError(
                    "Assistant currently supports at most 100 source profiles; use manual setup"
                )
            context = dict(
                profiles=list(profiles.values()), allow_combat=body["allow_combat"]
            )
            if scene_id:
                scene = self.live_status()["scenes"].get(scene_id)
                if not scene:
                    raise ValueError("Select an existing live scene")
                context = dict(scene=scene)
            config = dict(self.config)
            self.live_assistant_busy = True
            self.live_assistant_last = time.monotonic()
        try:
            with provider.observe_requests(
                self.usage.recorder("dm_assistant", "live_assistant", config)
            ):
                result = dm_assistant.generate(
                    config, instruction, context, review=bool(scene_id)
                )
            return dm_assistant.validate(
                result, profiles, body["allow_combat"], review=bool(scene_id)
            )
        finally:
            with self.lock:
                self.live_assistant_busy = False

    def persist_live(self):
        self.set_setting("live_encounter_journal", self.live_scenes)

    def live_for(self, npc):
        return next(
            (
                s["run"]
                for s in self.live_scenes.values()
                if s["run"]["status"]
                in ("active", "paused", "placing", "staged", "cleaning")
                and npc in s["actors"]
            ),
            None,
        )

    def live_status(self):
        with self.lock:
            scenes = copy.deepcopy(self.live_scenes)
            for s in scenes.values():
                s.pop("owner", None)
                for npc, row in s["actors"].items():
                    state = self.states.get(npc, {})
                    row["connected"] = time.monotonic() - state.get("seen", 0) < 4
                    row["mode"] = state.get("mode", "")
                    row["dead"] = bool(state.get("dead"))
                    row["combat"] = bool(state.get("combat"))
            return dict(
                scenes=scenes,
                ready=time.monotonic() - self.live_hello.get("seen", 0) < 4
                and self.live_hello.get("live_protocol") == 1,
                spawn_enabled=bool(self.config.get("allow_dm_spawn")),
            )

    def live_dm(self, dm):
        target = self.dms.get(dm, {})
        if (
            self.restoring
            or not self.config.get("allow_dm_spawn")
            or time.monotonic() - target.get("seen", 0) >= 3
            or target.get("live_protocol") != 1
        ):
            raise ValueError(
                "Select a connected, unpossessed DM with the updated live-encounter bridge"
            )
        return target

    def capture_live(self, dm):
        target = self.live_dm(dm)
        point = {
            k: target[k]
            for k in (
                "area_object",
                "area",
                "area_tag",
                "area_name",
                "x",
                "y",
                "z",
                "facing",
            )
        }
        if any(not math.isfinite(point[k]) for k in ("x", "y", "z", "facing")):
            raise ValueError("Invalid game position")
        now = time.monotonic()
        self.live_captures = {
            k: v for k, v in self.live_captures.items() if now - v["time"] < 900
        }
        if len(self.live_captures) >= 100:
            raise ValueError(
                "Too many marked locations; wait for older marks to expire"
            )
        token = secrets.token_hex(12)
        self.live_captures[token] = dict(
            point=point, session=target["session"], time=now
        )
        return dict(capture=token, point=point)

    def preview_live(self, value):
        if not isinstance(value, dict) or set(value) != {
            "dm",
            "name",
            "profile",
            "count",
            "blueprint",
            "spawn",
            "trigger",
            "public_facts",
            "goal",
            "boundaries",
            "reaction",
            "repeat",
        }:
            raise ValueError("Invalid live encounter draft")
        target = self.live_dm(value["dm"])
        if type(value["count"]) is not int or not 1 <= value["count"] <= 8:
            raise ValueError("Choose 1–8 creatures")
        if type(value["repeat"]) is not bool:
            raise ValueError("Choose whether the trigger repeats")
        blueprint = value["blueprint"]
        if not isinstance(blueprint, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]{0,15}", blueprint
        ):
            raise ValueError(
                "Blueprint: 1–16 lowercase letters, numbers or underscores"
            )
        profile = copy.deepcopy(self.store.get(value["profile"]))
        policy = reaction(value["reaction"])
        points = {}
        for key in ("spawn", "trigger"):
            capture = self.live_captures.get(value[key], {})
            if (
                time.monotonic() - capture.get("time", 0) > 900
                or capture.get("session") != target["session"]
            ):
                raise ValueError("Mark both locations in the current game session")
            points[key] = copy.deepcopy(capture["point"])
        a, b = points["spawn"], points["trigger"]
        if (
            a["area_object"] != b["area_object"]
            or math.dist(
                [a[k] for k in ("x", "y", "z")], [b[k] for k in ("x", "y", "z")]
            )
            > 20
        ):
            raise ValueError(
                "Spawn and trigger must be in the same area, within 20 metres"
            )
        spec = dict(
            name=text(value["name"], 100, True),
            profile=profile,
            count=value["count"],
            blueprint=blueprint,
            points=points,
            public_facts=text(value["public_facts"], 4000),
            goal=text(value["goal"], 2000),
            boundaries=text(value["boundaries"], 3000),
            reaction=policy,
            repeat=value["repeat"],
        )
        now = time.monotonic()
        self.live_previews = {
            k: v for k, v in self.live_previews.items() if now - v["time"] < 120
        }
        if len(self.live_previews) >= 30:
            raise ValueError("Too many previews; wait two minutes")
        token = secrets.token_hex(12)
        self.live_previews[token] = dict(spec=spec, session=target["session"], time=now)
        return dict(
            preview=token,
            spec=spec,
            expires_seconds=120,
            note="Preview only. Nothing spawned. Blueprint availability is checked by the game during placement.",
        )

    def live_send(self, scene, npc, kind, **fields):
        hello = self.live_hello
        if (
            time.monotonic() - hello.get("seen", 0) > 3
            or hello.get("session") != scene["run"]["session"]
            or hello.get("live_protocol") != 1
        ):
            raise ValueError("Live scene is not connected to its original game session")
        request = secrets.token_hex(12)
        cmd = dict(
            kind=kind,
            npc=npc,
            world=self.config["world_id"],
            session=hello["session"],
            expires=hello["tick"] + 5,
            request=request,
            scene=scene["run"]["template"]["id"],
            owner=scene["owner"],
            **fields,
        )
        self.pending[request] = dict(
            npc=npc, kind=kind, scene=cmd["scene"], time=time.monotonic()
        )
        try:
            self.redis.call(
                "LPUSH" if kind == "live_cleanup" else "RPUSH",
                self.prefix + ":commands",
                json.dumps(cmd),
            )
            self.redis.call("EXPIRE", self.prefix + ":commands", 10)
        except Exception:
            self.pending.pop(request, None)
            raise

    def place_live(self, preview, dm):
        target = self.live_dm(dm)
        entry = self.live_previews.get(preview, {})
        if (
            time.monotonic() - entry.get("time", 0) > 120
            or entry.get("session") != target["session"]
        ):
            raise ValueError("Preview expired or game restarted; preview again")
        if (
            sum(
                s["run"]["status"] not in ("cleaned", "expired")
                for s in self.live_scenes.values()
            )
            >= 10
        ):
            raise ValueError("Clean up existing live scenes first (maximum 10)")
        if not self.live_status()["ready"]:
            raise ValueError("Wait for the live encounter bridge before placing")
        spec = entry["spec"]
        connected = sum(
            time.monotonic() - s.get("seen", 0) < 4 for s in self.states.values()
        )
        if connected + spec["count"] > 32:
            raise ValueError("Not enough bound NPC slots (maximum 32)")
        self.live_previews.pop(preview)  # Single-use: retries never duplicate a cast.
        key = "live_" + secrets.token_hex(6)
        actors = {}
        for i in range(spec["count"]):
            npc = key + "_" + str(i + 1)
            profile = dict(spec["profile"], id=npc, mode="paused")
            profile["name"] = profile["name"][:75] + (
                " " + str(i + 1) if spec["count"] > 1 else ""
            )
            self.store.save(profile)
            actors[npc] = dict(
                name=profile["name"], placement="not submitted", cleanup=""
            )
        d = definition(
            dict(
                id=key,
                name=spec["name"],
                summary="",
                dm_notes="",
                location="",
                public_facts=spec["public_facts"],
                boundaries=spec["boundaries"],
                reaction=spec["reaction"],
                actors=[
                    dict(
                        npc=n,
                        role="Live encounter participant",
                        knowledge="",
                        goal=spec["goal"],
                    )
                    for n in actors
                ],
                stages=[dict(id="scene", name="Live scene", situation=spec["goal"])],
                outcomes=[dict(id="ended", name="Ended", description="")],
            )
        )
        run = dict(
            template=d,
            status="placing",
            stage="scene",
            outcome="",
            world=self.config["world_id"],
            session=target["session"],
            revision=secrets.token_hex(12),
            started=time.time(),
            updated=time.time(),
            events=[],
        )
        scene = dict(run=run, owner=secrets.token_hex(12), actors=actors, spec=spec)
        terminal = [
            k
            for k, s in self.live_scenes.items()
            if s["run"]["status"] in ("cleaned", "expired")
        ]
        for old in terminal[:-39]:
            self.live_scenes.pop(old)
        self.live_scenes[key] = scene
        self.encounter_log(run, "Placing temporary cast; the trigger is not armed.")
        self.persist_live()  # Record ownership before the first non-atomic game request.
        for npc, row in actors.items():
            try:
                self.live_send(
                    scene,
                    npc,
                    "live_spawn",
                    dm=dm,
                    dm_token=target["token"],
                    point=spec["points"]["spawn"],
                    blueprint=spec["blueprint"],
                    name=row["name"],
                    creature=creature_build(spec["profile"]),
                )
                row["placement"] = "awaiting confirmation"
            except (ValueError, OSError) as exc:
                row["placement"] = "submission failed: " + str(exc)
                run["status"] = "staged"
                break
        self.persist_live()
        return self.live_status()

    def live_ack(self, pending, event):
        scene = self.live_scenes.get(pending["scene"])
        if not scene:
            return
        row = scene["actors"][pending["npc"]]
        if pending["kind"] == "live_cleanup":
            row["cleanup"] = (
                "confirmed"
                if event.get("ok") == 1
                else "rejected; release possession and retry"
            )
            if event.get("ok") == 1:
                self.states.pop(pending["npc"], None)
            if all(a["cleanup"] == "confirmed" for a in scene["actors"].values()):
                scene["run"]["status"] = "cleaned"
                self.encounter_log(
                    scene["run"],
                    "Owned creatures removed. Profiles and memories retained.",
                )
        else:
            row["placement"] = (
                "confirmed"
                if event.get("ok") == 1
                else "rejected; check blueprint, location and available slots"
            )
            if scene["run"]["status"] == "placing" and not any(
                a["placement"] == "awaiting confirmation"
                for a in scene["actors"].values()
            ):
                scene["run"]["status"] = "staged"
        self.persist_live()

    def control_live(self, key, operation):
        scene = self.live_scenes.get(key)
        if not scene:
            raise ValueError("Unknown live scene")
        run = scene["run"]
        if run["status"] in ("expired", "cleaned"):
            raise ValueError("This live scene has ended; preview a new scene")
        if operation == "cleanup":
            run["status"] = (
                "cleaning"  # Stop renewing leases before any removal request.
            )
            self.persist_live()
            for npc, row in scene["actors"].items():
                if row["cleanup"] == "confirmed":
                    continue
                if any(
                    p.get("scene") == key
                    and p["npc"] == npc
                    and p["kind"] == "live_cleanup"
                    for p in self.pending.values()
                ):
                    continue
                self.generations[npc] = self.generations.get(npc, 0) + 1
                self.live_send(scene, npc, "live_cleanup")
                row["cleanup"] = "awaiting confirmation"
        elif operation == "pause":
            if run["status"] not in ("active", "paused"):
                raise ValueError("Scene is not active or paused")
            run["status"] = "paused"
            self.persist_live()
            failed = []
            for npc in scene["actors"]:
                try:
                    self.control(npc, "paused")
                except (ValueError, OSError):
                    failed.append(npc)
            self.encounter_log(
                run,
                "Trigger disabled; actor pause requests sent."
                + (
                    " Retry pause for unavailable actors: " + ", ".join(failed)
                    if failed
                    else ""
                ),
            )
        elif operation == "start":
            if run["status"] not in ("staged", "paused"):
                raise ValueError("Wait for placement confirmation before starting")
            for npc, row in scene["actors"].items():
                s = self.states.get(npc, {})
                if (
                    scene.get("checks", {}).get("enabled")
                    and s.get("encounter_protocol", 0) < 5
                ):
                    raise ValueError(
                        "Skill checks require the updated game scripts and a server restart"
                    )
                if (
                    run["template"]["reaction"].get("combat_mode") == "conversation"
                    and s.get("encounter_protocol", 0) < 3
                ):
                    raise ValueError(
                        "Conversation combat needs the updated game scripts and a server restart"
                    )
                if (
                    row["placement"] != "confirmed"
                    or time.monotonic() - s.get("seen", 0) > 3
                    or s.get("session") != run["session"]
                    or s.get("live_owner") != scene["owner"]
                    or s.get("possessed")
                    or s.get("dead")
                    or s.get("combat")
                ):
                    raise ValueError(
                        "All owned actors must be connected, alive, unpossessed and out of combat"
                    )
            try:
                for npc in scene["actors"]:
                    self.control(npc, "auto")
            except (ValueError, OSError):
                run["status"] = "paused"
                self.encounter_log(
                    run,
                    "Start incomplete; trigger remains disabled. Check actor modes and retry pause or cleanup.",
                )
                self.persist_live()
                raise ValueError(
                    "Could not start every actor; trigger remains disabled. Retry pause or cleanup."
                )
            run.update(status="active", started=time.time())
            run["activation_events"] = []
            self.encounter_observed.pop(key, None)
            scene["check_results"] = {}
            self.social_sync_at.pop(key, None)
            if "director" in scene:
                from .live_director import initial

                old = scene["director"]
                scene["director"] = dict(
                    initial(),
                    enabled=old["enabled"],
                    paused=old["paused"],
                    direction=old["direction"],
                    revision=old["revision"] + 1,
                )
                self.director_runtime.pop(key, None)
            self.encounter_log(
                run,
                (
                    "Started by DM; waiting for game trigger confirmation."
                    if run["template"]["reaction"]["enabled"]
                    else "Dialogue start requested; no proximity trigger configured."
                ),
            )
        else:
            raise ValueError("Unknown live scene operation")
        self.persist_live()
        return self.live_status()

    def tick_live(self, event):
        self.live_hello = dict(event, seen=time.monotonic())
        dirty = False
        for key, scene in self.live_scenes.items():
            run = scene["run"]
            if run["status"] in ("cleaned", "expired"):
                continue
            if run["session"] != event.get("session"):
                run["status"] = "expired"
                self.encounter_log(
                    run,
                    "Module restarted; temporary scene expired and will not respawn.",
                )
                dirty = True
                continue
            # Transport timeouts are explicitly retryable cleanup, never presumed success.
            for npc, row in scene["actors"].items():
                if row["cleanup"] == "awaiting confirmation" and not any(
                    p["npc"] == npc and p["kind"] == "live_cleanup"
                    for p in self.pending.values()
                ):
                    row["cleanup"] = "confirmation missing; retry cleanup"
                    dirty = True
                if row["placement"] == "awaiting confirmation" and not any(
                    p["npc"] == npc and p["kind"] == "live_spawn"
                    for p in self.pending.values()
                ):
                    row["placement"] = "confirmation missing; clean up and place again"
                    if run["status"] == "placing":
                        run["status"] = "staged"
                    dirty = True
            if (
                run["status"] == "active"
                and time.monotonic() - self.social_sync_at.get(key, 0) >= 2
            ):
                self.sync_social_checks(key, scene)
                self.social_sync_at[key] = time.monotonic()
            if run["status"] != "active" or not run["template"]["reaction"]["enabled"]:
                continue
            if time.monotonic() - self.live_sync_at.get(key, 0) < 2:
                continue
            states = [self.states.get(n, {}) for n in scene["actors"]]
            if any(
                time.monotonic() - s.get("seen", 0) > 3
                or s.get("mode") != "auto"
                or s.get("dead")
                or s.get("possessed")
                or s.get("live_owner") != scene["owner"]
                for s in states
            ):
                continue
            try:
                self.command(
                    next(iter(scene["actors"])),
                    "encounter_arm",
                    world=self.config["world_id"],
                    encounter=key,
                    token=str(run["started"]),
                    policy=run["template"]["reaction"],
                    actors=[
                        dict(npc=n, epoch=s["epoch"])
                        for n, s in zip(scene["actors"], states)
                    ],
                    live_owner=scene["owner"],
                    anchor=scene["spec"]["points"]["trigger"],
                    repeat=scene["spec"]["repeat"],
                    director_hold=self.director_npc_context(
                        next(iter(scene["actors"]))
                    ).get("holding", False)
                    or self.director_npc_context(next(iter(scene["actors"]))).get(
                        "finished", False
                    ),
                )
                self.live_sync_at[key] = time.monotonic()
            except (ValueError, OSError):
                pass
        if dirty:
            self.persist_live()

    def live_game_event(self, event):
        scene = self.live_scenes.get(event.get("encounter"))
        if not scene:
            return False
        run = scene["run"]
        if (
            run["status"] == "active"
            and event.get("world") == run["world"]
            and event.get("session") == run["session"]
            and event.get("token") == str(run["started"])
            and event.get("npc") in scene["actors"]
        ):
            status = event.get("status")
            labels = dict(
                director_finished="Director ended this activation peacefully",
                engaged="Opening delivered; player can reply naturally",
                negotiating="Combat warning delivered; waiting for a later player reply",
                peaceful="NPC backed down; activation ended peacefully",
                decision_rejected="Combat decision rejected by game checks",
                armed="Trigger armed",
                warning="Warning delivered",
                left="Player withdrew",
                attack="Attack ordered",
                finished="Warning ended",
                cancelled="Trigger cancelled; pause and restart after checking actors",
                warning_failed="Warning failed; no attack ordered",
                returned="Actor returned home",
                rearmed="Trigger reset",
                low_health="Actor retreating: low health",
                pursuit_limit="Actor retreating: pursuit limit",
                target_gone="Actor retreating: target gone",
                return_failed="Actor could not return; DM assistance needed",
            )
            if status in labels:
                if status == "director_finished" and "director" in scene:
                    scene["director"].update(
                        resolved=True, phase="finished", goals={}, error=""
                    )
                self.encounter_log(run, labels[status])
                self.encounter_observed[run["template"]["id"]] = labels[status]
                self.persist_live()
        return True
