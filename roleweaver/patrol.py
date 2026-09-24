"""Bounded patrol duties; movement uses the existing game-confirmed action path.

Only configuration is durable. A restart never replays an outstanding command.
Player conversations, possession and combat always take priority over a duty.
"""

import time

DEFAULT = dict(enabled=False, purpose="", route=[], dwell_seconds=30)
ACTIVE = ("pending", "running", "waiting for player")


def validate(value, allowed):
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
    return dict(value, route=list(route))


class PatrolService:
    def save_patrol(self, npc, value):
        self.store.get(npc)
        permissions = self.action_config["npcs"].get(npc, {})
        duty = validate(value, permissions.get("destinations", []))
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
            if job["status"] == "completed":
                runtime["index"] = (runtime["index"] + 1) % len(duty["route"])
                runtime["next"] = now + duty["dwell_seconds"]
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
        except (ValueError, OSError):
            runtime.update(halted=True, status="Dispatch failed; save patrol to retry")
            return
        self.action_jobs[npc]["patrol"] = True
        runtime.update(
            request=self.action_jobs[npc]["request"], status="Patrol requested"
        )
