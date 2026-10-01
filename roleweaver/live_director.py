"""Live-scene adapter for the autonomous director.

One background review at a time; network IO never holds the game lock. Frozen
scene/revision/fingerprint checks discard answers after new input or DM changes.
Raw player identities are not sent to the model. Existing dialogue safeguards
still review every NPC response and native scripts remain the action authority.
"""

import hashlib
import json
import time

from . import director, provider, safeguards
from .encounters import text


def initial():
    return dict(
        enabled=False,
        paused=False,
        revision=0,
        direction="",
        summary="",
        phase="waiting",
        goals={},
        decisions=[],
        reviews=0,
        error="",
        resolved=False,
    )


class LiveDirectorService:
    def director_observe(self, event):
        key = event.get("encounter")
        scene = self.director_scenes().get(key)
        if not scene:
            return
        run = scene["run"]
        if (
            run["status"] != "active"
            or event.get("world") != run["world"]
            or event.get("session") != run["session"]
            or event.get("token") != str(run["started"])
            or event.get("npc") != next(iter(scene["actors"]))
        ):
            return
        players = event.get("players")
        if (
            not isinstance(players, list)
            or len(players) > 32
            or any(not isinstance(p, str) or len(p) > 256 for p in players)
        ):
            return
        aliases = []
        for p in players:
            identity = hashlib.sha256((self.salt + p).encode()).hexdigest()[:24]
            aliases.append(
                "visitor-" + hashlib.sha256((key + identity).encode()).hexdigest()[:8]
            )
        self.director_presence[key] = dict(
            players=sorted(set(aliases)), seen=time.monotonic()
        )

    def init_director(self):
        self.director_busy = False
        self.director_poll_at = 0
        self.director_last_at = 0
        self.director_runtime = {}
        self.director_presence = {}
        self.director_turns = {}

    def director_chat(self, npc, player, event):
        """Retain engine eligibility, not a timer inferred from dialogue prose."""
        scene = next(
            (s for s in self.director_scenes().values() if npc in s["actors"]), None
        )
        state = self.states.get(npc, {})
        if (
            not scene
            or scene["run"]["status"] != "active"
            or event.get("session") != state.get("session")
            or event.get("epoch") != state.get("epoch")
            or not event.get("event_id")
            or type(event.get("combat_attack_ready")) is not int
            or event["combat_attack_ready"] not in (0, 1)
        ):
            return
        key = scene["run"]["template"]["id"]
        self.director_turns[npc] = dict(
            event_id=event["event_id"],
            activation=scene["run"]["started"],
            session=state["session"],
            epoch=state["epoch"],
            seen=time.monotonic(),
            observation=dict(
                participant="visitor-"
                + hashlib.sha256((key + player).encode()).hexdigest()[:8],
                attack_ready=event["combat_attack_ready"] == 1,
            ),
        )

    def director_before_reply(self, npc, turn, generation, started):
        """Review a current encounter turn before composing this same reply.

        Reuse the single director slot, budgets and stale-snapshot validation.
        Never hold the service lock during the provider request.
        Even a first refusal or payment offer must clear an earlier no-player
        hold; waiting until attack eligibility would prevent the warning itself.
        """
        with self.lock:
            if not turn.get("event_id") or self.restoring:
                return
            scene = next(
                (s for s in self.director_scenes().values() if npc in s["actors"]), None
            )
            if not scene or scene["run"]["status"] != "active":
                return
            d = scene.get("director", {})
            state = self.states.get(npc, {})
            observed = self.director_turns.get(npc, {})
            if (
                not d.get("enabled")
                or d.get("paused")
                or d.get("resolved")
                or npc != next(iter(scene["actors"]))
                or generation != self.generations.get(npc, 0)
                or state.get("session") != started.get("session")
                or state.get("epoch") != started.get("epoch")
                or observed.get("event_id") != turn.get("event_id")
                or observed.get("activation") != scene["run"]["started"]
                or observed.get("observation", {}).get("attack_ready")
                != turn.get("attack_ready")
                or time.monotonic() - observed.get("seen", 0) >= 120
            ):
                return
            key = scene["run"]["template"]["id"]
            runtime = self.director_runtime.setdefault(key, {})
            now = time.monotonic()
            if now < runtime.get("retry_after", 0) or (
                scene.get("scope") != "persistent" and d["reviews"] >= 60
            ):
                return
            if self.director_busy:
                runtime["priority"] = True
                return
            if not self.request_budget.admit("live-director"):
                runtime["retry_after"] = now + 10
                return
            context, fingerprint = self.director_context(key, scene)
            if fingerprint == runtime.get("fingerprint"):
                return
            self.director_busy = True
            runtime.pop("priority", None)
            self.director_last_at = now
            runtime["next"] = now + 10
            d["reviews"] += 1
            self.persist_director(scene)
            args = (
                key,
                scene["run"]["started"],
                d["revision"],
                fingerprint,
                context,
                dict(self.config),
            )
        self.director_review(*args)

    def director_control(self, body):
        if self.restoring:
            raise ValueError("Wait for restore to finish")
        if not isinstance(body, dict) or set(body) != {"id", "operation", "direction"}:
            raise ValueError("Invalid director control")
        scene = self.director_scenes().get(body["id"])
        if not scene or scene["run"]["status"] in ("cleaned", "expired", "cleaning"):
            raise ValueError("Select a current live scene")
        if (
            scene.get("scope") == "persistent"
            and not scene["run"]["template"]["automation"]["enabled"]
        ):
            raise ValueError(
                "Approve AI DM automation in the definition and start a new activation first"
            )
        op = body["operation"]
        if op not in ("enable", "pause", "resume", "direction"):
            raise ValueError("Unknown director control")
        direction = text(body["direction"], 2000)
        d = scene.setdefault("director", initial())
        if op in ("enable", "resume"):
            if self.config.get("provider") == "offline":
                raise ValueError(
                    "Configure an LLM before enabling autonomous direction"
                )
            p = scene["run"]["template"]["reaction"]
            if p["attack"] and p.get("combat_mode") != "conversation":
                raise ValueError(
                    "Use conversation-driven combat for autonomous direction; timed attacks are independent"
                )
            if any(
                self.states.get(n, {}).get("encounter_protocol", 0) < 4
                for n in scene["actors"]
            ):
                raise ValueError(
                    "Install the director game scripts and restart the server first"
                )
            if d["resolved"]:
                raise ValueError(
                    "Start a fresh scene activation before resuming its director"
                )
            d.update(enabled=True, paused=False, error="")
        elif op == "pause":
            d["paused"] = True
        else:
            d["direction"] = direction
        d["revision"] += 1
        d["goals"] = {}
        self.director_runtime.pop(body["id"], None)
        self.persist_director(scene)
        return (
            self.encounter_status()
            if scene.get("scope") == "persistent"
            else self.live_status()
        )

    def director_command_result(self, pending, ok):
        key = pending.get("encounter")
        scene = self.director_scenes().get(key)
        if (
            not scene
            or pending.get("token") != str(scene["run"]["started"])
            or "director" not in scene
        ):
            return
        if ok:
            scene["director"].update(
                resolved=True, phase="finished", goals={}, error=""
            )
            if scene.get("scope") == "persistent":
                self.finish_persistent_resolution(scene["run"])
        else:
            scene["director"].update(
                goals={},
                error="Game could not confirm resolution; combat decisions held while waiting for a fresh review.",
            )
            self.director_runtime[key] = {
                "next": time.monotonic() + 60,
                "retry_after": time.monotonic() + 60,
            }
        self.persist_director(scene)

    def director_context(self, key, scene):
        run = scene["run"]
        ids = list(scene["actors"])
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT id,npc,player,speaker,text FROM messages WHERE npc IN ("
                + ",".join("?" for _ in ids)
                + ") AND created>=? ORDER BY id DESC LIMIT 30",
                (*ids, run["started"]),
            ).fetchall()
        transcript = [
            dict(
                id=r["id"],
                npc=r["npc"],
                participant="visitor-"
                + hashlib.sha256((key + r["player"]).encode()).hexdigest()[:8],
                speaker=r["speaker"],
                text=r["text"][:1500],
            )
            for r in reversed(rows)
        ]
        actors = {}
        for n in ids:
            s = self.states.get(n, {})
            job = self.action_jobs.get(n, {})
            actors[n] = dict(
                name=scene["actors"][n]["name"],
                connected=time.monotonic() - s.get("seen", 0) < 4,
                dead=bool(s.get("dead")),
                combat=bool(s.get("combat")) and not bool(s.get("dead")),
                mode=s.get("mode"),
                action=dict(choice=job.get("choice"), status=job.get("status")),
            )
            turn = self.director_turns.get(n, {})
            actors[n]["last_player_reply"] = (
                turn["observation"]
                if turn
                and turn["activation"] == run["started"]
                and turn["session"] == s.get("session")
                and turn["epoch"] == s.get("epoch")
                and time.monotonic() - turn["seen"] < 120
                else None
            )
        p = self.director_presence.get(key, {})
        presence = (
            p.get("players", []) if time.monotonic() - p.get("seen", 0) < 12 else None
        )
        d = scene.setdefault("director", initial())
        context = dict(
            purpose=scene["spec"]["goal"],
            facts=scene["spec"]["public_facts"],
            boundaries=scene["spec"]["boundaries"],
            permissions=run["template"]["reaction"],
            direction=d["direction"],
            actors=actors,
            npc_actions={n: self.npc_combat_choices(n) for n in ids},
            confirmed_payments=[
                dict(
                    npc=r["npc"],
                    amount=r["amount"],
                    participant="visitor-"
                    + hashlib.sha256((key + r["player"]).encode()).hexdigest()[:8],
                )
                for r in self.payment_receipts
                if r["encounter"] == key and r["activation"] == run["started"]
            ],
            nearby_players=presence,
            dialogue=transcript,
            game_events=run.get("activation_events", run["events"])[-15:],
            social_policy=scene.get("checks", {"enabled": False}),
            social_checks=[
                dict(
                    npc=v["npc"],
                    participant=v.get("participant", "unknown"),
                    skill=v["skill"],
                    intent=v["intent"],
                    result=v["result"],
                )
                for v in scene.get("check_results", {}).values()
            ][-20:],
        )
        if scene.get("scope") == "persistent":
            context["progression"] = dict(
                current=run["stage"],
                stages=run["template"]["stages"],
                outcomes=run["template"]["outcomes"],
            )
        # PII scrubbing applies to the director as well as character dialogue.
        context = safeguards.scrub_tree(
            context, safeguards.settings(self.safeguard_policy)
        )
        fingerprint = hashlib.sha256(
            json.dumps(context, sort_keys=True).encode()
        ).hexdigest()
        context["previous_summary"] = d["summary"]
        return context, fingerprint

    def director_tick(self):
        with self.lock:
            now = time.monotonic()
            if self.restoring or self.director_busy or now < self.director_poll_at:
                return
            self.director_poll_at = now + 2
            for key, scene in sorted(
                self.director_scenes().items(),
                key=lambda row: not self.director_runtime.get(row[0], {}).get(
                    "priority", False
                ),
            ):
                d = scene.get("director", {})
                if (
                    scene["run"]["status"] != "active"
                    or not d.get("enabled")
                    or d.get("paused")
                    or d.get("resolved")
                ):
                    continue
                if any(n in self.busy for n in scene["actors"]):
                    continue  # Let dialogue and its skill check finish before directing its outcome.
                runtime = self.director_runtime.setdefault(key, {})
                if (
                    len(self.busy) >= 3
                    or now < runtime.get("retry_after", 0)
                    or (
                        not runtime.get("priority")
                        and (
                            now < runtime.get("next", 0)
                            or now < self.director_last_at + 10
                        )
                    )
                ):
                    continue
                context, fingerprint = self.director_context(key, scene)
                if fingerprint == runtime.get("fingerprint"):
                    continue
                if not any(a["connected"] for a in context["actors"].values()):
                    continue
                if scene.get("scope") != "persistent" and all(
                    a["connected"] and a["dead"] for a in context["actors"].values()
                ):
                    d.update(
                        resolved=True,
                        phase="finished",
                        goals={},
                        summary="All encounter actors are dead, confirmed by the game.",
                    )
                    self.persist_director(scene)
                    continue
                if scene.get("scope") != "persistent" and d["reviews"] >= 60:
                    d.update(
                        paused=True,
                        goals={},
                        error="60-review safety limit reached; DM may start a fresh activation.",
                    )
                    self.persist_director(scene)
                    continue
                if not self.request_budget.admit("live-director"):
                    runtime["next"] = now + 10
                    continue
                self.director_busy = True
                runtime.pop("priority", None)
                self.director_last_at = now
                runtime["next"] = now + 10
                d["reviews"] += 1
                self.persist_director(scene)
                self.pool.submit(
                    self.director_review,
                    key,
                    scene["run"]["started"],
                    d["revision"],
                    fingerprint,
                    context,
                    dict(self.config),
                )
                break

    def director_review(self, key, activation, revision, fingerprint, context, config):
        try:
            with provider.observe_requests(
                self.usage.recorder(
                    "dm_assistant",
                    (
                        "persistent_director"
                        if context.get("progression")
                        else "live_director"
                    ),
                    config,
                )
            ):
                result = director.evaluate(config, context)
            with self.lock:
                scene = self.director_scenes().get(key)
                if not scene:
                    return
                d = scene.get("director", {})
                if (
                    self.restoring
                    or config != self.config
                    or scene["run"]["status"] != "active"
                    or scene["run"]["started"] != activation
                    or d.get("revision") != revision
                    or d.get("paused")
                    or d.get("resolved")
                ):
                    return
                _, current = self.director_context(key, scene)
                if current != fingerprint:
                    return
                result = director.validate(
                    result,
                    scene["actors"],
                    context.get("progression"),
                    context.get("npc_actions"),
                )
                d.update(
                    summary=result["summary"],
                    phase=result["phase"],
                    error="",
                    goals=result["goals"] if result["operation"] == "continue" else {},
                )
                d["decisions"] = (
                    d["decisions"]
                    + [
                        dict(
                            time=time.time(),
                            operation=result["operation"],
                            reason=result["reason"],
                        )
                    ]
                )[-20:]
                self.director_runtime[key]["fingerprint"] = fingerprint
                if result["operation"] == "hold":
                    d["error"] = "Director is holding: " + result["reason"]
                elif result["operation"] == "stage":
                    scene["run"]["stage"] = result["stage"]
                    self.encounter_log(
                        scene["run"],
                        "AI DM advanced to approved stage: " + result["stage"],
                    )
                elif result["operation"] == "resolve":
                    if scene.get("scope") == "persistent":
                        d["pending_outcome"] = result["outcome"]
                    if any(
                        self.states.get(n, {}).get("combat")
                        and not self.states.get(n, {}).get("dead")
                        for n in scene["actors"]
                    ):
                        d["error"] = "Resolution deferred until combat ends."
                    elif scene["run"]["template"]["reaction"]["enabled"]:
                        self.command(
                            next(iter(scene["actors"])),
                            "encounter_end",
                            world=self.config["world_id"],
                            encounter=key,
                            token=str(activation),
                            **self.scene_authority(scene),
                        )
                        d["phase"] = "resolving"
                    else:
                        d.update(resolved=True, phase="finished")
                        if scene.get("scope") == "persistent":
                            self.finish_persistent_resolution(scene["run"])
                for npc, choice in result.get("actions", {}).items():
                    self.run_action(npc, choice)
                    self.encounter_log(
                        scene["run"],
                        "AI DM requested approved action: "
                        + npc
                        + " "
                        + choice
                        + "; awaiting game confirmation.",
                    )
                self.persist_director(scene)
        except Exception as exc:
            from .diagnostics_log import record

            record(self, "provider_failed", exc, phase="director")
            with self.lock:
                scene = self.director_scenes().get(key)
                if (
                    scene
                    and scene["run"]["started"] == activation
                    and scene.get("director", {}).get("revision") == revision
                ):
                    scene["director"].update(
                        goals={},
                        error="Director review unavailable; new combat decisions held. Retrying after 60 seconds.",
                    )
                    self.director_runtime.setdefault(key, {})["next"] = (
                        time.monotonic() + 60
                    )
                    self.director_runtime[key]["retry_after"] = self.director_runtime[
                        key
                    ]["next"]
                    self.director_runtime[key].pop("fingerprint", None)
                    self.persist_director(scene)
        finally:
            with self.lock:
                self.director_busy = False

    def director_npc_context(self, npc):
        scene = next(
            (s for s in self.director_scenes().values() if npc in s["actors"]), None
        )
        d = scene.get("director", {}) if scene else {}
        if not d.get("enabled"):
            return {}
        return dict(
            phase=d.get("phase"),
            finished=d.get("resolved", False),
            goal=(
                d.get("goals", {}).get(npc, "")
                if not d.get("paused") and not d.get("error")
                else ""
            ),
            holding=bool(
                scene["run"]["status"] != "active"
                or d.get("paused")
                or d.get("error")
                or d.get("phase") == "resolving"
                or not d.get("summary")
            ),
        )
