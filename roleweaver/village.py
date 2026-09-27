"""Low-frequency village routines. No background LLM planning or durable jobs.

Saved home anchors the leash across restarts; player/DM activity wins. Social
visits reuse the guarded two-turn check-in system and its request limits.
"""

import random
import time

DEFAULT = dict(enabled=False, radius=8, activity="normal", greetings=True, visits=True)
ACTIVE = ("pending", "running", "waiting for player")
INTERVALS = {
    "quiet": (120, 240),
    "normal": (60, 120),
    "lively": (30, 60),
    "testing": (5, 5),
}


def policy(value=None):
    if value is None:
        return dict(DEFAULT)
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError("Invalid Village Life settings")
    if any(type(value[k]) is not bool for k in ("enabled", "greetings", "visits")):
        raise ValueError("Village Life switches must be enabled or disabled")
    if type(value["radius"]) is not int or not 2 <= value["radius"] <= 12:
        raise ValueError("Village wandering radius must be 2–12 metres")
    if not isinstance(value["activity"], str) or value["activity"] not in INTERVALS:
        raise ValueError("Choose Quiet, Normal, Lively or Testing")
    return dict(value)


class VillageService:
    def village_tick(self, npc, event):
        p = self.action_config["npcs"].get(npc, {})
        v = p.get("village", DEFAULT)
        if not v["enabled"]:
            return
        now = time.monotonic()
        r = self.village_runtime.setdefault(npc, {})
        if r.get("session") != event.get("session"):
            r.clear()
            r.update(
                session=event.get("session"),
                next=now
                + (5 if v["activity"] == "testing" else random.uniform(15, 45)),
                steps=0,
            )
        home = self.action_config["destinations"].get(p.get("home"))
        reason = ""
        if r.get("halted"):
            reason = "Stopped; save permissions to resume Village Life"
        elif not p.get("enabled") or not home:
            reason = "Enable controlled actions and choose a saved home"
        elif self.restoring or event.get("village_protocol") != 1:
            reason = "Waiting for updated game bridge"
        elif self.encounter_for(npc) or p.get("patrol", {}).get("enabled"):
            reason = "Encounter or patrol duties take priority"
        elif event.get("mode") != "auto" or any(
            event.get(k) for k in ("dead", "combat", "possessed")
        ):
            reason = "Paused for DM control, combat or death"
        elif (
            event.get("conversation_active")
            or npc in self.busy
            or (self.checkin and npc in self.checkin["pair"])
        ):
            reason = "Conversation takes priority"
        elif (event.get("area_resref"), event.get("area_tag")) != (
            home["area"],
            home["area_tag"],
        ):
            reason = "Outside home area; no automatic area transitions"
        if reason:
            r.update(
                status=reason, next=now + (5 if v["activity"] == "testing" else 30)
            )
            return
        if any(
            j.get("visit_peer") == npc
            and j.get("status") in ACTIVE
            and now - j.get("started", now) < 40
            for j in self.action_jobs.values()
        ):
            r.update(
                status="Waiting for an approaching NPC visitor",
                next=now + (5 if v["activity"] == "testing" else 20),
            )
            return
        job = self.action_jobs.get(npc, {})
        if job.get("status") in ACTIVE:
            if job.get("village") and now - job.get("started", now) > 45:
                self.stop_action(npc)
                r.update(halted=True, status="Action confirmation timed out; stopped")
            else:
                r["status"] = "Finishing current action"
            return
        if r.get("request"):
            if job.get("request") == r.pop("request"):
                if job.get("status") == "completed":
                    r["need_walk"] = job.get("choice") not in (
                        "village:wander",
                        "village:home",
                    )
                    r["next"] = now + random.uniform(*INTERVALS[v["activity"]])
                    r["status"] = "Activity completed; taking a short break"
                else:
                    r["next"] = max(r["next"], now + 90)
                    r["status"] = (
                        "Taking a break after an interrupted or unavailable action"
                    )
        if now < r["next"] or now - self.action_last.get(npc, 0) < self.action_cooldown(
            npc
        ):
            return
        r["next"] = now + random.uniform(*INTERVALS[v["activity"]])
        distance = (
            (event.get("x", home["x"]) - home["x"]) ** 2
            + (event.get("y", home["y"]) - home["y"]) ** 2
        ) ** 0.5
        if distance > v["radius"] + 1:
            r["status"] = (
                f"{distance:.1f} m from home ({v['radius']} m radius). Use Return Home or choose a closer Home location."
            )
            return
        options = ["wander", "rest"]
        if r["steps"] >= 3 and distance > 1.5:
            options = ["home"]
        elif r.get("need_walk", True):
            options = ["wander"]
        else:
            options = ["rest"]
            if v["greetings"] and now - r.get("greeted", -1000) >= 300:
                options.append("greet")
            available = self.action_choices(npc)
            options += [a["id"] for a in available if a["id"].startswith("sit:")]
            if v["visits"] and now - r.get("visited", -1000) >= self.visit_cooldown(
                npc
            ):
                options += [a["id"] for a in available if a["id"].startswith("visit:")]
        if v["activity"] == "testing":
            visits = [o for o in options if o.startswith("visit:")]
            if visits:
                options = visits
        choice = random.choice(options)
        if choice == "rest":
            r["need_walk"] = True
            r["status"] = "Resting quietly; a walk is next"
            return
        try:
            if ":" in choice:
                self.run_action(npc, choice, village=True)
            else:
                request = self.command(
                    npc,
                    "controlled_action",
                    world=self.config["world_id"],
                    action="village",
                    target=choice,
                    village=1,
                    village_delay=5 if v["activity"] == "testing" else 20,
                    village_home=home,
                    village_radius=v["radius"],
                )
                self.action_jobs[npc] = dict(
                    request=request,
                    choice="village:" + choice,
                    status="pending",
                    session=event["session"],
                    started=now,
                    village=True,
                )
                self.action_last[npc] = now
            if choice == "greet":
                r["greeted"] = now
            if choice.startswith("visit:"):
                r["visited"] = now
            r["steps"] = 0 if choice == "home" else r["steps"] + 1
            r.update(
                request=self.action_jobs[npc]["request"],
                status="Village activity: " + choice,
            )
        except (ValueError, OSError):
            r.update(
                next=now + 90, status="Activity unavailable; waiting before retrying"
            )
