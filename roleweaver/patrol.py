"""Bounded patrol duties; movement uses the existing game-confirmed action path.

Only configuration is durable. A restart never replays an outstanding command.
Player conversations, possession and combat always take priority over a duty.
"""

import time
from .checkins import CheckinService

DEFAULT = dict(enabled=False, purpose="", route=[], dwell_seconds=30)
ACTIVE = ("pending", "running", "waiting for player")


def validate(value, allowed):
    if isinstance(value, dict):
        value = dict(value)
        checkins = value.pop("checkins", {})
        cooldown = value.pop("checkin_cooldown", 300)
    else:
        checkins, cooldown = {}, 300
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError("Invalid patrol settings")
    if type(value["enabled"]) is not bool:
        raise ValueError("Choose whether patrol is enabled")
    if not isinstance(value["purpose"], str) or len(value["purpose"]) > 1000:
        raise ValueError("Purpose must be at most 1000 characters")
    route = value["route"]
    if (
        not isinstance(route, list)
        or len(route) > 20
        or any(not isinstance(x, str) or x not in allowed for x in route)
    ):
        raise ValueError("Choose up to 20 permitted walk destinations")
    if value["enabled"] and len(route) < 2:
        raise ValueError("An enabled patrol needs at least two stops")
    if (
        type(value["dwell_seconds"]) is not int
        or not 20 <= value["dwell_seconds"] <= 600
    ):
        raise ValueError("Time at each stop must be 20–600 seconds")
    import re

    if (
        not isinstance(checkins, dict)
        or len(checkins) > 20
        or any(
            k not in route
            or not isinstance(v, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", v)
            for k, v in checkins.items()
        )
        or type(cooldown) is not int
        or not 60 <= cooldown <= 3600
    ):
        raise ValueError(
            "Check-ins need route stops, valid NPC IDs and a cooldown of 60–3600 seconds"
        )
    return dict(value, route=list(route), checkins=checkins, checkin_cooldown=cooldown)


class PatrolService(CheckinService):
    def save_patrol(self, npc, value):
        self.store.get(npc)
        permissions = self.action_config["npcs"].get(npc, {})
        duty = validate(value, permissions.get("destinations", []))
        for target in duty["checkins"].values():
            if target == npc:
                raise ValueError("Choose another NPC for a check-in")
            self.store.get(target)
        if self.checkin and npc in self.checkin["pair"]:
            # Changing the game epoch also invalidates speech already queued in Redis.
            self.stop_action(npc)
        if duty["enabled"] and not permissions.get("enabled"):
            raise ValueError("Enable controlled actions first")
        job = self.action_jobs.get(npc, {})
        if job.get("patrol") and job.get("status") in ACTIVE:
            self.stop_action(npc)
        permissions = dict(permissions, patrol=duty)
        self.action_config["npcs"][npc] = permissions
        self.persist_actions()
        self.patrol_runtime.pop(npc, None)
        return self.action_status()

    def patrol_tick(self, npc, event):
        """Called under the service lock for a fresh, authoritative state event."""
        if self.encounter_for(npc):
            self.patrol_runtime.setdefault(npc, {})[
                "status"
            ] = "Reserved for DM encounter"
            return
        duty = self.action_config["npcs"].get(npc, {}).get("patrol", DEFAULT)
        if not duty["enabled"]:
            return
        now = time.monotonic()
        runtime = self.patrol_runtime.setdefault(npc, {})
        if runtime.get("session") != event.get("session"):
            runtime.clear()
            runtime.update(session=event.get("session"), index=0, next=now + 5)
        if self.restoring or event.get("awareness_protocol") != 1:
            runtime["status"] = "Waiting for updated game bridge"
            return
        if self.checkin and npc in self.checkin["pair"]:
            runtime["status"] = "NPC check-in in progress"
            runtime["next"] = now + duty["dwell_seconds"]
            return
        if (
            event.get("mode") != "auto"
            or event.get("possessed")
            or event.get("dead")
            or event.get("combat")
        ):
            runtime["status"] = "Suspended: DM control, pause, death or combat"
            return
        if event.get("conversation_active") or npc in self.busy:
            runtime["status"] = "Waiting for player conversation"
            runtime["next"] = now + duty["dwell_seconds"]
            return
        if runtime.get("halted"):
            runtime["status"] = "Stopped; save patrol settings to restart"
            return
        job = self.action_jobs.get(npc, {})
        if job.get("request") == runtime.get("request") and runtime.get("request"):
            if job["status"] in ACTIVE:
                if now - job["started"] > 45:
                    runtime.update(
                        halted=True, status="No completion received; patrol stopped"
                    )
                else:
                    runtime["status"] = "Walking to patrol stop"
                return
            runtime.pop("request", None)
            if job["status"] in ("completed", "timed out"):
                # A game-confirmed timeout ended movement; it is safe to continue.
                # Missing acknowledgements still halt above.
                stop = duty["route"][runtime["index"]]
                peer = duty.get("checkins", {}).get(stop)
                other = self.states.get(peer, {})
                if (job["status"] == "completed" and peer and time.monotonic() - other.get("seen", 0) < 3
                        and other.get("area") == event.get("area")
                        and (other.get("x", 0) - event.get("x", 0)) ** 2
                        + (other.get("y", 0) - event.get("y", 0)) ** 2 > 25
                        and runtime.get("reapproaches", 0) < 2):
                    runtime["reapproaches"] = runtime.get("reapproaches", 0) + 1
                    runtime["next"] = now + 20
                    runtime["status"] = "Contact moved; approaching their current position"
                    return
                runtime.pop("reapproaches", None)
                runtime["index"] = (runtime["index"] + 1) % len(duty["route"])
                runtime["next"] = now + duty["dwell_seconds"]
                self.start_checkin(npc, stop, duty)
            elif job["status"] == "interrupted":
                runtime["next"] = now + duty["dwell_seconds"]
            else:
                runtime.update(
                    halted=True, status="Movement failed; save patrol to retry"
                )
                return
        if now < runtime["next"]:
            runtime["status"] = "Waiting at patrol stop"
            return
        target = duty["route"][runtime["index"]]
        if "walk:" + target not in {a["id"] for a in self.action_choices(npc)}:
            runtime["status"] = "Waiting for movement permission or another action"
            return
        try:
            self.run_action(npc, "walk:" + target, patrol=True)
        except ValueError:
            # A missing, busy, or distant contact must not trap the entire route.
            runtime.pop("reapproaches", None)
            runtime.update(index=(runtime["index"] + 1) % len(duty["route"]),
                           next=now + duty["dwell_seconds"],
                           status="Skipped unavailable patrol contact; continuing route")
            return
        except OSError:
            # Delivery is uncertain. Do not issue overlapping movement commands.
            runtime.update(halted=True, status="Command delivery uncertain; patrol stopped")
            return
        self.action_jobs[npc]["patrol"] = True
        runtime.update(
            request=self.action_jobs[npc]["request"], status="Patrol requested"
        )
