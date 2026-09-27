"""Permissions and choices for visible targets. References are game-issued, not IDs.

Object tags are retained separately for DM configuration, never sent as perception
to the model. No arbitrary object-use, scripts, unlocking or inventory access.
"""

import re
from . import perception

DEFAULT = dict(
    approach=False, doors=False, talk=False, receive=False, radius=8, seat_tags=[]
)
KINDS = ("approach", "open_door", "close_door", "sit", "visit")


def conversation_request(speech):
    """Conservative choice restriction, never a command or permission grant.

    The model handles meaning and target selection. Recognisable social requests
    must not silently fall back to an unrelated saved destination.
    """
    return bool(
        isinstance(speech, str)
        and re.search(
            r"\b(?:talk|speak|chat|converse)\s+(?:to|with)\b|"
            r"\bcheck\s+(?:in\s+)?(?:on|with)\b|"
            r"\b(?:go|walk|head)\b[^.!?\n]{0,60}\b(?:talk|speak|chat|visit)\b",
            speech,
            re.IGNORECASE,
        )
    )


def dialogue_choices(available, speech):
    if not conversation_request(speech):
        return available
    # Approach only moves; it cannot start a conversation. A visit has both steps.
    excluded = (
        "walk:",
        "lead:",
        "home:",
        "approach:",
        "sit:",
        "open_door:",
        "close_door:",
    )
    return [a for a in available if not a["id"].startswith(excluded)]


def policy(value=None):
    if value is None:
        return dict(DEFAULT, seat_tags=[])
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError("Invalid nearby behaviour permissions")
    if any(
        type(value[k]) is not bool for k in ("approach", "doors", "talk", "receive")
    ):
        raise ValueError("Choose enabled or disabled for each nearby behaviour")
    if type(value["radius"]) is not int or not 2 <= value["radius"] <= 12:
        raise ValueError("Nearby movement distance must be 2–12 metres")
    tags = value["seat_tags"]
    if (
        not isinstance(tags, list)
        or len(tags) > 30
        or any(
            not isinstance(t, str) or not t or len(t) > 128 or not t.isprintable()
            for t in tags
        )
        or len(set(tags)) != len(tags)
    ):
        raise ValueError("Choose up to 30 unique chair tags")
    return dict(value, seat_tags=list(tags))


def targets(raw, area_wide=False):
    """Separate, bounded transport metadata; never merged into LLM perception."""
    result = {}
    if not isinstance(raw, list):
        return result
    for row in raw[: 256 if area_wide else 24]:
        if not isinstance(row, dict):
            continue
        ref = row.get("ref", "")
        if not isinstance(ref, str) or not re.fullmatch(r"v[1-9][0-9]{0,9}", ref):
            continue
        public = perception.observations([row], area_wide=area_wide)
        if not public:
            continue
        item = public[0]
        tag = row.get("tag", "")
        item["tag"] = tag if isinstance(tag, str) and len(tag) <= 128 else ""
        peer = row.get("peer", "")
        item["peer"] = (
            peer
            if isinstance(peer, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,23}", peer)
            else ""
        )
        result[ref] = item
    return result


def choices(saved, state, can_visit):
    p = saved.get("nearby", DEFAULT)
    if (
        not saved.get("enabled")
        or state.get("nearby_protocol") != 1
        or not perception.snapshot(state)["available"]
    ):
        return []
    out = []
    for ref, item in state.get("nearby_targets", {}).items():
        if (
            item["distance"] > p["radius"]
            or item.get("player")
            or item.get("condition") == "dead"
        ):
            continue
        description = (
            f'{item["label"]} ({item["distance"]} m, {item.get("bearing", "nearby")})'
        )
        verbs = []
        if p["approach"]:
            verbs.append(("approach", "Walk near "))
        if p["doors"] and item["kind"] == "door" and item.get("usable"):
            verbs.append(
                ("close_door", "Close ")
                if item.get("open") == "open"
                else ("open_door", "Open ")
            )
        if (
            item["kind"] == "placeable"
            and item["tag"]
            and item["tag"] in p["seat_tags"]
        ):
            verbs.append(("sit", "Sit on "))
        if p["talk"] and item["peer"] and can_visit(item["peer"]):
            verbs.append(
                (
                    "visit",
                    "Go to the CURRENT LIVE POSITION and then start a brief conversation with ",
                )
            )
        out.extend(
            dict(id=verb + ":" + ref, description=text + description)
            for verb, text in verbs
        )
    return out
