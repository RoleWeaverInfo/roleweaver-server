"""DM-authored situations and manual lifecycle, independent of any particular plot.

Definitions are reusable. Runs take a snapshot so later edits cannot silently
rewrite a live scene. Only DM API calls advance stages or record an outcome;
model text never changes encounter state or grants game-action permissions.
"""

import copy
import math
import secrets
import time
from .actions import identifier

LIVE = ("active", "paused", "waiting")


def automation(value=None):
    defaults = dict(
        enabled=False, resume_after_restart=True, repeat_after_restart=False
    )
    if value is None:
        return defaults
    if (
        not isinstance(value, dict)
        or set(value) != set(defaults)
        or any(type(v) is not bool for v in value.values())
    ):
        raise ValueError("Invalid persistent automation settings")
    return dict(value)


DEFAULT_REACTION = dict(
    enabled=False,
    attack=False,
    combat_mode="timed",
    combat_conditions="",
    opening="A moment, traveler. I would like a word.",
    trigger_radius=5,
    leave_radius=10,
    grace_seconds=15,
    pursuit_radius=20,
    retreat_hp_percent=25,
    warning="Leave this place. Move away now and we will not attack.",
)


def reaction(value=None):
    if value is None:
        return dict(DEFAULT_REACTION)
    optional = {
        "pursuit_radius",
        "retreat_hp_percent",
        "combat_mode",
        "combat_conditions",
        "opening",
    }
    if not isinstance(value, dict) or not set(DEFAULT_REACTION) - optional <= set(
        value
    ) <= set(DEFAULT_REACTION):
        raise ValueError("Invalid encounter trigger settings")
    result = dict(DEFAULT_REACTION, **value)
    result["opening"] = text(result["opening"], 500, True)
    if result["combat_mode"] not in ("timed", "conversation", "greeting"):
        raise ValueError("Choose timed or conversation combat")
    if result["combat_mode"] == "greeting" and (
        not result["enabled"] or result["attack"]
    ):
        raise ValueError(
            "Greeting triggers require proximity enabled and combat disabled"
        )
    result["combat_conditions"] = text(result["combat_conditions"], 2000)
    if result["combat_mode"] == "conversation" and (
        not result["enabled"] or not result["attack"] or not result["combat_conditions"]
    ):
        raise ValueError(
            "Conversation combat requires explicit attack permission and DM conditions"
        )
    if "pursuit_radius" not in value:
        result["pursuit_radius"] = max(20, value.get("leave_radius", 10))
    for key in ("enabled", "attack"):
        if type(result[key]) is not bool:
            raise ValueError(
                "Trigger and attack permissions must be enabled or disabled"
            )
    for key, low, high in (
        ("trigger_radius", 1, 8),
        ("leave_radius", 2, 30),
        ("grace_seconds", 5, 120),
        ("pursuit_radius", 0, 60),
        ("retreat_hp_percent", 0, 90),
    ):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError("Invalid " + key)
    if result["leave_radius"] <= result["trigger_radius"]:
        raise ValueError("Leave distance must be larger than trigger distance")
    if result["pursuit_radius"] and result["pursuit_radius"] < result["leave_radius"]:
        raise ValueError(
            "Pursuit limit must be at least the leave distance, or 0 to disable"
        )
    result["warning"] = text(result["warning"], 500, True)
    return result


def text(value, limit, required=False):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (required and not value.strip())
    ):
        raise ValueError("Missing or oversized encounter text")
    return value.strip()


def definition(value):
    keys = {
        "id",
        "name",
        "summary",
        "public_facts",
        "dm_notes",
        "boundaries",
        "location",
        "actors",
        "stages",
        "outcomes",
    }
    if not isinstance(value, dict) or not keys <= set(value) <= keys | {
        "reaction",
        "automation",
        "checks",
    }:
        raise ValueError("Invalid encounter definition")
    result = {
        k: text(value[k], limit, k == "name")
        for k, limit in (
            ("name", 100),
            ("summary", 2000),
            ("public_facts", 4000),
            ("dm_notes", 6000),
            ("boundaries", 3000),
        )
    }
    result["reaction"] = reaction(value.get("reaction"))
    from .social_checks import policy

    result["automation"] = automation(value.get("automation"))
    result["checks"] = policy(value.get("checks"))
    if result["checks"]["enabled"] and not result["reaction"]["enabled"]:
        raise ValueError("Enable the proximity trigger before using social checks")
    if (
        result["automation"]["enabled"]
        and result["reaction"]["attack"]
        and result["reaction"]["combat_mode"] != "conversation"
    ):
        raise ValueError("AI-directed combat must use conversation-driven decisions")
    result.update(id=identifier(value["id"]), location=value["location"])
    if value["location"] != "":
        identifier(value["location"])
    for key, fields in (
        ("actors", {"npc": 24, "role": 200, "knowledge": 4000, "goal": 2000}),
        ("stages", {"id": 24, "name": 100, "situation": 3000}),
        ("outcomes", {"id": 24, "name": 100, "description": 2000}),
    ):
        rows = value[key]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
            raise ValueError("Supply 1–8 " + key)
        clean = []
        seen = set()
        for row in rows:
            optional = {"combatant", "opening"} if key == "actors" else set()
            if (
                not isinstance(row, dict)
                or not set(fields) <= set(row) <= set(fields) | optional
            ):
                raise ValueError("Invalid encounter " + key)
            item = {
                k: text(row[k], limit, k in ("npc", "id", "name", "role"))
                for k, limit in fields.items()
            }
            if key == "actors":
                if type(row.get("combatant", True)) is not bool:
                    raise ValueError(
                        "Actor combat permission must be enabled or disabled"
                    )
                item["combatant"] = row.get("combatant", True)
                if "opening" in row:
                    item["opening"] = text(row["opening"], 300)
            identity = identifier(item["npc"] if key == "actors" else item["id"])
            if identity in seen:
                raise ValueError("Duplicate encounter " + key)
            seen.add(identity)
            clean.append(item)
        result[key] = clean
    return result


def settings(value=None):
    if value is None:
        return dict(templates={}, runs={})
    if not isinstance(value, dict) or set(value) != {"templates", "runs"}:
        raise ValueError("Invalid encounter data")
    if any(not isinstance(value[k], dict) or len(value[k]) > 50 for k in value):
        raise ValueError("Maximum 50 encounters")
    templates = {identifier(k): definition(v) for k, v in value["templates"].items()}
    if any(k != v["id"] for k, v in templates.items()):
        raise ValueError("Encounter ID mismatch")
    runs = {}
    occupied = set()
    for key, raw in value["runs"].items():
        if (
            key not in templates
            or not isinstance(raw, dict)
            or not {
                "template",
                "status",
                "stage",
                "outcome",
                "world",
                "session",
                "revision",
                "started",
                "updated",
                "events",
            }
            <= set(raw)
            <= {
                "template",
                "status",
                "stage",
                "outcome",
                "world",
                "session",
                "revision",
                "started",
                "updated",
                "events",
                "owner",
                "director",
                "check_results",
                "activation_events",
                "recovery_reason",
            }
        ):
            raise ValueError("Invalid encounter run")
        run = copy.deepcopy(raw)
        run["template"] = definition(raw["template"])
        if run["template"]["id"] != key or run["status"] not in (
            *LIVE,
            "completed",
            "cancelled",
        ):
            raise ValueError("Invalid encounter state")
        if run["stage"] not in {s["id"] for s in run["template"]["stages"]}:
            raise ValueError("Invalid encounter stage")
        if run["outcome"] not in {"", *(o["id"] for o in run["template"]["outcomes"])}:
            raise ValueError("Invalid encounter outcome")
        if (run["status"] == "completed") != bool(run["outcome"]):
            raise ValueError("Outcome requires completion")
        for field in ("world", "session", "revision"):
            text(run[field], 128, True)
        for field in ("started", "updated"):
            if (
                type(run[field]) not in (int, float)
                or not math.isfinite(run[field])
                or run[field] < 0
            ):
                raise ValueError("Invalid encounter time")
        if not isinstance(run["events"], list) or len(run["events"]) > 50:
            raise ValueError("Invalid encounter log")
        run["events"] = [text(e, 500) for e in run["events"]]
        if "owner" in run:
            text(run["owner"], 128, True)
        if "recovery_reason" in run:
            text(run["recovery_reason"], 500)
        if "director" in run:
            from .persistent_director import validate_runtime

            validate_runtime(run)
        actors = {a["npc"] for a in run["template"]["actors"]}
        if run["status"] in LIVE:
            if occupied & actors:
                raise ValueError("An NPC cannot join two live encounters")
            occupied.update(actors)
        runs[key] = run
    return dict(templates=templates, runs=runs)


class EncounterService:
    def init_encounters(self):
        self.encounter_sync_at = {}
        self.encounter_release_at = {}
        self.encounter_observed = {}
        self.encounters = settings(self.setting("encounters", None))
        self.encounter_revision = secrets.token_hex(12)
        for run in self.encounters["runs"].values():
            if run["status"] == "active":
                auto = run["template"]["automation"]
                run["status"] = (
                    "waiting"
                    if auto["enabled"] and auto["resume_after_restart"]
                    else "paused"
                )
                self.encounter_log(
                    run,
                    (
                        "Companion restarted; waiting for actors to recover."
                        if run["status"] == "waiting"
                        else "Companion restarted; DM must resume this encounter."
                    ),
                )
        self.persist_encounters()

    def encounter_log(self, run, message):
        run["updated"] = time.time()
        run["revision"] = secrets.token_hex(12)
        run["events"] = (
            run["events"]
            + [time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()) + " — " + message]
        )[-50:]
        if "activation_events" in run:
            run["activation_events"] = (run["activation_events"] + [run["events"][-1]])[
                -50:
            ]

    def persist_encounters(self):
        settings(
            self.encounters
        )  # Validate without invalidating active adapter references.
        self.encounter_revision = secrets.token_hex(12)
        self.set_setting("encounters", self.encounters)

    def encounter_status(self):
        with self.lock:
            actors = {
                a["npc"]
                for d in list(self.encounters["templates"].values())
                + [
                    r["template"]
                    for r in self.encounters["runs"].values()
                    if r["status"] in LIVE
                ]
                for a in d["actors"]
            }
            return copy.deepcopy(
                dict(
                    self.encounters,
                    revision=self.encounter_revision,
                    readiness={
                        k: self.persistent_readiness(d)
                        for k, d in self.encounters["templates"].items()
                    },
                    actors={
                        n: {
                            "connected": time.monotonic()
                            - self.states.get(n, {}).get("seen", 0)
                            < 4,
                            **{
                                k: self.states.get(n, {}).get(k)
                                for k in (
                                    "mode",
                                    "combat",
                                    "dead",
                                    "possessed",
                                    "area",
                                    "retreat_protocol",
                                    "combat_phase",
                                )
                            },
                            "action": self.action_jobs.get(n, {}).get("status", ""),
                        }
                        for n in actors
                    },
                )
            )

    def encounter_for(self, npc):
        live = self.live_for(npc) if hasattr(self, "live_scenes") else None
        if live:
            return live
        return next(
            (
                run
                for run in self.encounters["runs"].values()
                if run["status"] in LIVE
                and any(a["npc"] == npc for a in run["template"]["actors"])
            ),
            None,
        )

    def encounter_context(self, npc):
        run = self.encounter_for(npc)
        if not run or run["world"] != self.config["world_id"]:
            return {}
        d = run["template"]
        actor = next(a for a in d["actors"] if a["npc"] == npc)
        stage = next(s for s in d["stages"] if s["id"] == run["stage"])
        # Deliberate allowlist: no DM notes, other actors' knowledge or future stages/outcomes.
        return dict(
            name=d["name"],
            status=run["status"],
            public_facts=d["public_facts"],
            boundaries=d["boundaries"],
            trigger_policy=d["reaction"],
            game_observation=self.encounter_observed.get(
                d["id"], "No trigger event confirmed"
            ),
            role=actor["role"],
            knowledge=actor["knowledge"],
            goal=actor["goal"],
            stage=stage["name"],
            situation=stage["situation"],
            direction=self.director_npc_context(npc),
        )

    def encounter_check_revision(self, revision):
        if revision != self.encounter_revision:
            raise ValueError(
                "Encounters changed; reload before saving or controlling them"
            )

    def save_encounter(self, value, revision):
        self.encounter_check_revision(revision)
        d = definition(value)
        if d["id"].startswith("live_"):
            raise ValueError("The live_ prefix is reserved for temporary encounters")
        for actor in d["actors"]:
            self.store.get(actor["npc"])
        if d["location"] and d["location"] not in self.action_config["destinations"]:
            raise ValueError("Choose a recorded location")
        if (
            d["id"] not in self.encounters["templates"]
            and len(self.encounters["templates"]) >= 50
        ):
            raise ValueError("Maximum 50 encounters")
        self.encounters["templates"][d["id"]] = d
        self.persist_encounters()
        return self.encounter_status()

    def delete_encounter(self, key, revision):
        self.encounter_check_revision(revision)
        if self.encounters["runs"].get(key, {}).get("status") in LIVE:
            raise ValueError("End or cancel the encounter before deleting it")
        if key not in self.encounters["templates"]:
            raise ValueError("Unknown encounter")
        self.encounters["templates"].pop(key)
        self.encounters["runs"].pop(key, None)
        self.persist_encounters()
        return self.encounter_status()

    def spawn_encounter_cast(self, key, dm, revision):
        """Spawn absent cast members using the existing validated temporary spawn path.

        Requests are individually acknowledged by the game. This is intentionally
        not an atomic batch: report partial submission and never delete creatures
        as a rollback. Repeated clicks skip pending or already connected actors.
        """
        self.encounter_check_revision(revision)
        if key not in self.encounters["templates"]:
            raise ValueError("Save an encounter first")
        if self.encounters["runs"].get(key, {}).get("status") in LIVE:
            raise ValueError(
                "Finish or cancel the current run before spawning its cast"
            )
        if self.restoring or not self.config.get("allow_dm_spawn"):
            raise ValueError("DM spawning is disabled")
        target = self.dms.get(dm, {})
        if time.monotonic() - target.get("seen", 0) >= 3:
            raise ValueError(
                "Select a connected, unpossessed DM for the spawn location"
            )
        cast = self.encounters["templates"][key]["actors"]
        for actor in cast:
            self.store.get(actor["npc"])
            if self.encounter_for(actor["npc"]):
                raise ValueError("An actor is reserved by another encounter")
        results = []
        for actor in cast:
            npc = actor["npc"]
            if time.monotonic() - self.states.get(npc, {}).get("seen", 0) < 4:
                results.append(dict(npc=npc, status="Already connected; left in place"))
                continue
            if any(v["npc"] == npc for v in self.pending.values()):
                results.append(
                    dict(npc=npc, status="Command pending; wait for confirmation")
                )
                continue
            try:
                self.spawn_at_dm(
                    npc,
                    dm,
                    "rw_custom",
                    (
                        "persistent"
                        if self.encounters["templates"][key]["automation"]["enabled"]
                        else "temporary"
                    ),
                )
                results.append(
                    dict(npc=npc, status="Spawn requested; awaiting game confirmation")
                )
            except (ValueError, OSError) as exc:
                results.append(dict(npc=npc, status="Not submitted: " + str(exc)))
                break
        return dict(self.encounter_status(), spawn_results=results)

    def encounter_ready(self, d):
        session = None
        leader = self.states.get(d["actors"][0]["npc"], {})
        for actor in d["actors"]:
            npc = actor["npc"]
            self.store.get(npc)
            s = self.states.get(npc, {})
            if (
                any(not a.get("combatant", True) for a in d["actors"])
                and s.get("encounter_protocol", 0) < 7
            ):
                raise ValueError(
                    "Install the noncombatant encounter bridge (protocol 7): " + npc
                )
            if (
                d["automation"]["enabled"]
                or d["checks"]["enabled"]
                or d["reaction"]["combat_mode"] == "conversation"
            ) and s.get("encounter_protocol", 0) < 6:
                raise ValueError(
                    "Install the persistent AI DM bridge (protocol 6): " + npc
                )
            if (
                time.monotonic() - s.get("seen", 0) > 3
                or s.get("mode") != "auto"
                or s.get("possessed")
                or s.get("dead")
                or s.get("combat")
                or npc in self.busy
            ):
                raise ValueError(
                    "All actors must be connected, idle, living and in AUTO: " + npc
                )
            if session is not None and session != s["session"]:
                raise ValueError("Actors are in different game sessions")
            session = s["session"]
            if (
                d["reaction"]["enabled"]
                and leader.get("area_resref")
                and s.get("area_resref")
            ):
                if (leader.get("area_resref"), leader.get("area_tag")) != (
                    s.get("area_resref"),
                    s.get("area_tag"),
                ):
                    raise ValueError("Place trigger actors in the same area: " + npc)
                if (
                    all(k in s and k in leader for k in ("x", "y"))
                    and math.hypot(s["x"] - leader["x"], s["y"] - leader["y"]) > 30
                ):
                    raise ValueError(
                        "Place trigger actors within 30 metres of the spokesperson: "
                        + npc
                    )
            if d["location"]:
                point = self.action_config["destinations"].get(d["location"], {})
                if (
                    point.get("world") != self.config["world_id"]
                    or point.get("area") != s.get("area_resref")
                    or point.get("area_tag") != s.get("area_tag")
                ):
                    raise ValueError(
                        "Place every actor in the encounter location's area first"
                    )
        return session

    def interrupt_encounter_actors(self, run):
        for actor in run["template"]["actors"]:
            npc = actor["npc"]
            self.generations[npc] = self.generations.get(npc, 0) + 1
            self.cancel_checkin(npc, "DM encounter control")
            s = self.states.get(npc, {})
            if (
                time.monotonic() - s.get("seen", 0) < 3
                and not s.get("possessed")
                and not s.get("combat")
            ):
                # Bump the game epoch to reject speech already queued before the change.
                try:
                    self.command(npc, "controlled_stop")
                except (OSError, ValueError):
                    pass

    def control_encounter(self, key, operation, revision, stage="", outcome=""):
        self.encounter_check_revision(revision)
        if key not in self.encounters["templates"]:
            raise ValueError("Unknown encounter")
        current = self.encounters["runs"].get(key)
        run = copy.deepcopy(current)
        if operation in ("start", "arm"):
            if run and run["status"] in LIVE:
                raise ValueError("Encounter already running or paused")
            d = copy.deepcopy(self.encounters["templates"][key])
            if any(self.encounter_for(a["npc"]) for a in d["actors"]):
                raise ValueError("An actor is reserved by another encounter")
            if operation == "arm" and not d["automation"]["enabled"]:
                raise ValueError(
                    "Enable AI DM automation before arming unattended recovery"
                )
            session = "awaiting-game" if operation == "arm" else self.encounter_ready(d)
            if (
                operation == "start"
                and d["reaction"]["enabled"]
                and any(
                    self.states[a["npc"]].get("encounter_protocol", 0) < 2
                    for a in d["actors"]
                )
            ):
                raise ValueError(
                    "Update the game bridge before enabling encounter triggers"
                )
            run = dict(
                template=d,
                status="waiting" if operation == "arm" else "active",
                stage=d["stages"][0]["id"],
                outcome="",
                world=self.config["world_id"],
                session=session,
                revision="new",
                started=time.time(),
                updated=time.time(),
                events=[],
            )
            self.prepare_persistent_runtime(run)
            message = (
                "Armed by DM; will start when the saved actors and bridge are ready."
                if operation == "arm"
                else "Started by DM. Shared scene for all players; no rewards or creatures created."
            )
        else:
            if not run or run["status"] not in LIVE:
                raise ValueError("No live encounter")
            if operation == "pause":
                run["status"] = "paused"
                message = "Paused by DM."
            elif operation == "resume":
                if run["world"] != self.config["world_id"]:
                    raise ValueError("Encounter belongs to a different world")
                run["session"] = self.encounter_ready(run["template"])
                run["status"] = "active"
                self.prepare_persistent_runtime(run, reset=False)
                message = "Resumed by DM."
            elif operation == "stage":
                if run["status"] != "active":
                    raise ValueError("Resume before changing stage")
                if stage not in {s["id"] for s in run["template"]["stages"]}:
                    raise ValueError("Choose a defined stage")
                run["stage"] = stage
                message = "DM set stage: " + stage
            elif operation == "complete":
                if outcome not in {o["id"] for o in run["template"]["outcomes"]}:
                    raise ValueError("Choose a defined outcome")
                run["status"] = "completed"
                run["outcome"] = outcome
                message = (
                    "DM recorded outcome: "
                    + outcome
                    + ". No automatic game transaction."
                )
            elif operation == "cancel":
                run["status"] = "cancelled"
                message = "Cancelled by DM; memories retained."
            else:
                raise ValueError("Unknown encounter operation")
        if "director" in run:
            run["director"]["revision"] += 1
            run["director"]["goals"] = {}
        self.director_runtime.pop(key, None)
        self.encounter_log(run, message)
        self.encounters["runs"][key] = run
        self.persist_encounters()
        if operation in ("pause", "cancel", "complete"):
            for actor in run["template"]["actors"]:
                if not self.states.get(actor["npc"], {}).get("combat"):
                    continue
                try:
                    self.command(
                        actor["npc"],
                        "encounter_release",
                        world=self.config["world_id"],
                        token=str(run["started"]),
                    )
                except (ValueError, OSError):
                    pass
        self.interrupt_encounter_actors(run)
        return self.encounter_status()

    def encounter_session(self, event):
        self.recover_persistent_encounters(event)
        changed = False
        for run in self.encounters["runs"].values():
            if run["status"] == "active" and (
                run["world"] != event.get("world")
                or run["session"] != event.get("session")
            ):
                run["status"] = "paused"
                self.encounter_log(run, "Game session changed; DM must resume.")
                self.interrupt_encounter_actors(run)
                changed = True
        if changed:
            self.persist_encounters()

    def retreat_encounter_actor(self, key, npc, destination, revision):
        self.encounter_check_revision(revision)
        run = self.encounters["runs"].get(key, {}) or self.live_scenes.get(key, {}).get(
            "run", {}
        )
        if run.get("status") not in LIVE or npc not in {
            a["npc"] for a in run["template"]["actors"]
        }:
            raise ValueError("Choose an actor in a live encounter")
        if run["world"] != self.config["world_id"]:
            raise ValueError("Resume this encounter in the current world first")
        p = self.action_config["npcs"].get(npc, {})
        if not p.get("enabled") or destination not in p.get("destinations", []):
            raise ValueError(
                "Approve this walk destination in Controlled Actions first"
            )
        s = self.states.get(npc, {})
        if (
            s.get("retreat_protocol") != 1
            or s.get("mode") != "auto"
            or s.get("possessed")
            or s.get("dead")
        ):
            raise ValueError(
                "Retreat requires the updated bridge and a living, unpossessed AUTO actor"
            )
        self.generations[npc] = self.generations.get(npc, 0) + 1
        request = self.command(
            npc,
            "controlled_action",
            action="retreat",
            target=destination,
            destination=self.action_config["destinations"][destination],
            world=self.config["world_id"],
            listener="",
        )
        self.action_jobs[npc] = dict(
            request=request,
            choice="retreat:" + destination,
            status="pending",
            session=s["session"],
            started=time.monotonic(),
        )
        self.encounter_log(
            run,
            "DM requested retreat for "
            + npc
            + " to "
            + destination
            + "; awaiting game confirmation.",
        )
        self.persist_encounters()
        return self.encounter_status()

    def sync_encounter_reactions(self, event):
        """Renew a short game lease. Loss of companion connectivity disarms timers."""
        now = time.monotonic()
        for key, run in self.encounters["runs"].items():
            policy = run["template"]["reaction"]
            if (
                run["status"] != "active"
                or not policy["enabled"]
                or run["session"] != event.get("session")
            ):
                continue
            if now - self.encounter_sync_at.get(key, 0) < 2:
                continue
            cast = run["template"]["actors"]
            states = [self.states.get(a["npc"], {}) for a in cast]
            if any(
                now - s.get("seen", 0) > 3
                or s.get("encounter_protocol", 0) < 2
                or (
                    any(not a.get("combatant", True) for a in cast)
                    and s.get("encounter_protocol", 0) < 7
                )
                or s.get("mode") != "auto"
                or s.get("possessed")
                or s.get("dead")
                for s in states
            ):
                continue
            self.encounter_sync_at[key] = now
            try:
                self.command(
                    cast[0]["npc"],
                    "encounter_arm",
                    world=self.config["world_id"],
                    encounter=key,
                    token=str(run["started"]),
                    policy=policy,
                    actors=[
                        dict(
                            npc=a["npc"],
                            epoch=s["epoch"],
                            combatant=a.get("combatant", True),
                            opening=a.get("opening", ""),
                        )
                        for a, s in zip(cast, states)
                    ],
                    persistent_owner=run.get("owner", ""),
                    director_hold=self.director_npc_context(cast[0]["npc"]).get(
                        "holding", False
                    ),
                    repeat=not run["template"]["automation"]["enabled"],
                )
                self.sync_social_checks(key, self.persistent_scene(key, run))
            except (ValueError, OSError):
                pass

    def encounter_game_event(self, event):
        run = self.encounters["runs"].get(event.get("encounter"))
        if (
            not run
            or event.get("world") != self.config["world_id"]
            or event.get("session") != run["session"]
            or event.get("token") != str(run["started"])
            or event.get("npc") not in {a["npc"] for a in run["template"]["actors"]}
        ):
            return
        status = event.get("status")
        descriptions = {
            "armed": "Trigger armed",
            "engaged": "Opening delivered; player can reply naturally",
            "negotiating": "Combat warning delivered; waiting for a later player reply",
            "peaceful": "NPC backed down; activation ended peacefully",
            "director_finished": "Director ended this activation peacefully",
            "decision_rejected": "Combat decision rejected by game checks",
            "warning": "Warning delivered; grace period started",
            "left": "Target withdrew; no attack ordered",
            "attack": "Grace expired; game ordered the cast to attack the warned player",
            "finished": "Grace expired; warning-only encounter finished",
            "cancelled": "Trigger cancelled: actor, target or companion unavailable",
            "warning_failed": "Warning could not be delivered; no attack ordered",
            "low_health": "Low health: returning to starting position",
            "pursuit_limit": "Pursuit boundary reached: returning to starting position",
            "target_gone": "Combat target unavailable: returning to starting position",
            "returned": "Returned to starting position; waiting for the encounter to reset",
            "rearmed": "Encounter reset after 10 quiet seconds; ready for another approach",
            "return_failed": "Return timed out or area changed; DM assistance needed",
        }
        if status not in descriptions:
            return
        message = descriptions[status]
        if status in (
            "low_health",
            "pursuit_limit",
            "target_gone",
            "returned",
            "return_failed",
        ):
            npc = event.get("npc")
            if npc not in {a["npc"] for a in run["template"]["actors"]}:
                return
            message = str(npc) + ": " + message
        if self.encounter_observed.get(event["encounter"]) == message:
            return
        self.encounter_observed[event["encounter"]] = message
        if status == "director_finished":
            self.finish_persistent_resolution(run)
        self.encounter_log(run, message)
        self.persist_encounters()

    def reconcile_encounter_combat(self, npc, event):
        """Release an orphaned native movement lock after companion restart/restore."""
        key = event.get("combat_encounter")
        token = event.get("combat_token")
        if not key or not token:
            return
        run = self.encounters["runs"].get(key, {}) or self.live_scenes.get(key, {}).get(
            "run", {}
        )
        if (
            run.get("status") == "active"
            and run.get("session") == event.get("session")
            and str(run.get("started")) == token
        ):
            return
        now = time.monotonic()
        if now - self.encounter_release_at.get(npc, 0) < 2:
            return
        self.encounter_release_at[npc] = now
        try:
            self.command(
                npc, "encounter_release", world=self.config["world_id"], token=token
            )
        except (ValueError, OSError):
            pass
