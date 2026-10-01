"""NWN adapter: classify, dispatch one idempotent roll, await confirmation.

No network or game wait holds the shared lock. A persisted attempt is reused after
a missing acknowledgement; the native cache prevents rerolling that attempt.
"""

import hashlib
import threading
import time
from . import social_checks, provider


class SocialCheckService:
    def init_social_checks(self):
        self.social_waiters = {}
        self.social_sync_at = {}

    def save_social_checks(self, body):
        if not isinstance(body, dict) or set(body) != {"id", "settings"}:
            raise ValueError("Invalid social check request")
        scene = self.live_scenes.get(body["id"])
        if not scene or scene["run"]["status"] not in ("staged", "paused"):
            raise ValueError("Pause the scene before changing skill checks")
        scene["checks"] = social_checks.policy(body["settings"])
        self.persist_director(scene)
        return self.live_status()

    def sync_social_checks(self, key, scene):
        if scene["run"]["status"] != "active":
            return
        settings = social_checks.policy(scene.get("checks"))
        for npc in scene["actors"]:
            s = self.states.get(npc, {})
            if s.get("encounter_protocol", 0) < 5:
                continue
            try:
                self.command(
                    npc,
                    "social_setup",
                    world=self.config["world_id"],
                    encounter=key,
                    token=str(scene["run"]["started"]),
                    **self.scene_authority(scene),
                    settings=settings,
                )
            except (ValueError, OSError):
                pass

    def resolve_social_check(
        self, npc, player, listener, turn, generation, started, speech, history, config
    ):
        with self.lock:
            scene = next(
                (
                    s
                    for s in self.director_scenes().values()
                    if npc in s["actors"] and s["run"]["status"] == "active"
                ),
                None,
            )
            settings = social_checks.policy(scene.get("checks") if scene else None)
            if not settings["enabled"]:
                return {}
            key = scene["run"]["template"]["id"]
            activation = scene["run"]["started"]
            previous = []
            for old_skill in social_checks.SKILLS:
                old_id = hashlib.sha256(
                    f"{key}:{activation}:{npc}:{player}:{old_skill}".encode()
                ).hexdigest()[:24]
                old = scene.get("check_results", {}).get(old_id, {})
                if old.get("result"):
                    previous.append(dict(old["result"], intent=old["intent"]))
            if self.states.get(npc, {}).get(
                "encounter_protocol", 0
            ) < 5 or not turn.get("event_id"):
                raise ValueError("Social checks need the updated bridge")
            if not self.request_budget.admit("social:" + player):
                raise ValueError("Social check request limit reached")
            context = dict(
                speech=speech,
                history=history[-8:],
                encounter=self.encounter_context(npc),
                previous_checks=previous,
            )
        with provider.observe_requests(
            self.usage.recorder(npc, "social_check", config)
        ):
            attempt = social_checks.classify(config, context, settings)
        skill = attempt["skill"]
        attempt_id = hashlib.sha256(
            f"{key}:{activation}:{npc}:{player}:{skill}".encode()
        ).hexdigest()[:24]
        with self.lock:
            current = self.director_scenes().get(key)
            if (
                not current
                or current["run"]["status"] != "active"
                or current["run"]["started"] != activation
                or generation != self.generations.get(npc, 0)
                or self.states.get(npc, {}).get("session") != started["session"]
                or self.states.get(npc, {}).get("epoch") != started["epoch"]
            ):
                raise ValueError("Social check became stale")
            if skill == "none":
                return dict(
                    required=False, previous_checks=previous, limits=settings["limits"]
                )
            ledger = current.setdefault("check_results", {})
            entry = ledger.get(attempt_id)
            if entry and entry.get("result"):
                entry["reuse_count"] = entry.get("reuse_count", 0) + 1
                self.persist_director(scene)
                return dict(
                    entry["result"],
                    required=True,
                    reused=True,
                    intent=entry["intent"],
                    limits=settings["limits"],
                )
            if not entry:
                if len(ledger) >= 128:
                    raise ValueError("Scene social-check limit reached")
                entry = ledger[attempt_id] = dict(
                    npc=npc,
                    participant="visitor-"
                    + hashlib.sha256((key + player).encode()).hexdigest()[:8],
                    skill=skill,
                    dc=settings["skills"][skill]["dc"],
                    intent=attempt["intent"],
                    created=time.time(),
                    result=None,
                )
                self.persist_director(
                    scene
                )  # Persist intent before dispatch, never reroll on a lost reply.
            wake = threading.Event()
            self.social_waiters[attempt_id] = dict(
                event=wake,
                npc=npc,
                key=key,
                token=str(activation),
                session=started["session"],
                epoch=started["epoch"],
                error=False,
            )
            try:
                request = self.command(
                    npc,
                    "social_roll",
                    world=self.config["world_id"],
                    encounter=key,
                    token=str(activation),
                    **self.scene_authority(current),
                    listener=listener,
                    combat_event=turn["event_id"],
                    skill=skill,
                    attempt=attempt_id,
                )
                self.social_waiters[attempt_id]["request"] = request
            except Exception:
                self.social_waiters.pop(attempt_id, None)
                raise
        try:
            if not wake.wait(8):
                raise ValueError(
                    "Game did not confirm the skill check; no outcome assumed"
                )
            with self.lock:
                result = entry.get("result")
                if not result:
                    raise ValueError("Game rejected the skill check")
                return dict(
                    result,
                    required=True,
                    reused=False,
                    intent=entry["intent"],
                    limits=settings["limits"],
                )
        finally:
            with self.lock:
                self.social_waiters.pop(attempt_id, None)

    def social_result(self, event):
        attempt = event.get("attempt")
        waiter = self.social_waiters.get(attempt)
        if not waiter or any(
            event.get(k) != waiter[k] for k in ("npc", "session", "epoch", "token")
        ):
            return
        if event.get("world") != self.config["world_id"] or event.get(
            "request"
        ) != waiter.get("request"):
            return
        scene = self.director_scenes().get(waiter["key"])
        if not scene or str(scene["run"]["started"]) != waiter["token"]:
            return
        entry = scene.get("check_results", {}).get(attempt)
        if (
            not entry
            or event.get("skill") != entry["skill"]
            or event.get("dc") != entry["dc"]
        ):
            return
        if any(
            type(event.get(k)) is not int
            for k in ("roll", "modifier", "total", "success")
        ):
            return
        if (
            not 1 <= event["roll"] <= 20
            or event["total"] != event["roll"] + event["modifier"]
            or event["success"] != int(event["total"] >= entry["dc"])
        ):
            return
        entry["result"] = {
            k: event[k] for k in ("skill", "dc", "roll", "modifier", "total", "success")
        }
        entry["confirmed"] = time.time()
        self.persist_director(scene)
        waiter["event"].set()

    def social_rejected(self, pending):
        waiter = self.social_waiters.get(pending.get("attempt"))
        if waiter:
            waiter["event"].set()
