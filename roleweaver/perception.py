"""Bounded, read-only observations shared by dialogue and the DM inspector.

The game decides visibility. This second boundary drops unknown fields, hides
player names and prevents stale or malformed snapshots from becoming model context.
Observations never become action permissions or automatic long-term memories.
"""

import math
import time

KINDS = ("character", "door", "container", "placeable")
CONDITIONS = ("uninjured", "injured", "badly injured", "dead")
BEARINGS = (
    "ahead",
    "ahead-left",
    "left",
    "behind-left",
    "behind",
    "behind-right",
    "right",
    "ahead-right",
)


def label(value):
    return "".join(c for c in str(value)[:80] if c.isprintable()).strip()


def observations(value, area_wide=False):
    if not isinstance(value, list):
        return []
    result = []
    descriptions = 0
    for raw in value[: 256 if area_wide else 24]:
        if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
            continue
        distance = raw.get("distance")
        if (
            type(distance) not in (int, float)
            or not math.isfinite(distance)
            or not 0 <= distance <= (100000 if area_wide else 12)
        ):
            continue
        if raw.get("dm") or raw.get("possessed"):
            continue
        kind = raw["kind"]
        player = kind == "character" and raw.get("player") in (True, 1)
        item = dict(
            kind=kind,
            label="Unidentified traveler" if player else label(raw.get("label", kind)),
            distance=round(distance, 1),
        )
        if raw.get("bearing") in BEARINGS:
            item["bearing"] = raw["bearing"]
        if kind == "character":
            item["player"] = player
            if isinstance(raw.get("appearance"), str):
                item["appearance"] = label(raw["appearance"])
            # Only NPC public Examine text. Player identity stays undisclosed.
            if (
                not player
                and descriptions < 12
                and isinstance(raw.get("description"), str)
            ):
                item["description"] = "".join(
                    c for c in raw["description"][:240] if c.isprintable()
                ).strip()
                descriptions += 1
            if raw.get("condition") in CONDITIONS:
                item["condition"] = raw["condition"]
            if raw.get("activity") in ("fighting", "not fighting"):
                item["activity"] = raw["activity"]
            if raw.get("attitude") in ("hostile", "friendly", "neutral"):
                item["attitude"] = raw["attitude"]
            if not player and raw.get("merchant") in (True, 1):
                item["merchant"] = True
        else:
            if type(raw.get("usable")) in (bool, int) and raw["usable"] in (0, 1):
                item["usable"] = bool(raw["usable"])
            if kind in ("door", "container") and raw.get("open") in ("open", "closed"):
                item["open"] = raw["open"]
        result.append(item)
    return result


def snapshot(state, now=None):
    now = time.monotonic() if now is None else now
    age = max(0, now - state.get("seen", 0))
    current = age < 4
    area_wide = state.get("perception_protocol") == 3
    rich = state.get("perception_protocol") in (2, 3)
    if rich:
        tick, observed = state.get("tick"), state.get("perception_tick")
        current = (
            current
            and type(tick) is int
            and type(observed) is int
            and 0 <= tick - observed <= 3
        )
    if not current:
        return dict(available=False, reason="No fresh game observation", objects=[])
    result = dict(
        available=True,
        detail="detailed" if rich else "basic",
        radius_metres=None if area_wide else 12,
        scope="current area, line of sight" if area_wide else "nearby",
        truncated=bool(state.get("perception_truncated")) if area_wide else False,
        area=label(state.get("area", "")),
        objects=observations(state.get("surroundings", []), area_wide=area_wide),
    )
    if state.get("self_condition") in CONDITIONS:
        result["self_condition"] = state["self_condition"]
    result["self_activity"] = "fighting" if state.get("combat") else "not fighting"
    result["coverage"] = (
        "Current-area line of sight; walls and visibility rules exclude hidden objects. Up to 256 visible objects from 1024 area candidates. The scan is incomplete if truncated is true. Directions are relative to facing at observation time."
        if area_wide
        else "Partial view: at most 24 nearest candidates; unseen or out-of-range objects are omitted. Directions are relative to the NPC's facing at observation time."
    )
    return result
