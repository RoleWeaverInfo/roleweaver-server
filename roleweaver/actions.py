"""DM-authored action permissions. Model choices are data, never executable code."""

import json
import math
import re
from . import patrol

GESTURES = ("greet", "bow", "salute")
DEFAULT_POLICY = dict(
    enabled=False,
    destinations=[],
    gestures=[],
    lead_destinations=[],
    home="",
    shop=False,
)
LEGACY_POLICY_KEYS = {"enabled", "destinations", "gestures"}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", value):
        raise ValueError(
            "Use a lowercase ID starting with a letter, then letters, numbers or underscores (maximum 24)."
        )
    return value


def destination(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid destination")
    out = {
        k: value.get(k)
        for k in ("id", "name", "world", "area", "area_tag", "x", "y", "z", "facing")
    }
    identifier(out["id"])
    for key, limit in (("name", 80), ("world", 128), ("area", 32), ("area_tag", 128)):
        if (
            not isinstance(out[key], str)
            or not out[key].strip()
            or len(out[key]) > limit
        ):
            raise ValueError("Invalid destination " + key)
    for key in ("x", "y", "z", "facing"):
        if (
            type(out[key]) not in (int, float)
            or not math.isfinite(out[key])
            or abs(out[key]) > 100000
        ):
            raise ValueError("Invalid destination coordinate")
        out[key] = float(out[key])
    return out


def policy(value, destinations):
    duty = value.get("patrol") if isinstance(value, dict) else None
    if isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != "patrol"}
    if (
        not isinstance(value, dict)
        or set(value) != set(DEFAULT_POLICY)
        or type(value["enabled"]) is not bool
    ):
        raise ValueError("Invalid action permissions")
    for key, allowed in (
        ("destinations", destinations),
        ("lead_destinations", destinations),
        ("gestures", GESTURES),
    ):
        if (
            not isinstance(value[key], list)
            or len(value[key]) > 100
            or any(not isinstance(x, str) or x not in allowed for x in value[key])
            or len(set(value[key])) != len(value[key])
        ):
            raise ValueError("Invalid allowed " + key)
    if (
        not isinstance(value["home"], str)
        or (value["home"] and value["home"] not in destinations)
        or type(value["shop"]) is not bool
    ):
        raise ValueError("Choose a saved home and a valid shop permission")
    result = {k: list(v) if isinstance(v, list) else v for k, v in value.items()}
    if duty is not None:
        result["patrol"] = patrol.validate(duty, result["destinations"])
    return result


def migrate_policy(value):
    if isinstance(value, dict) and set(value) == LEGACY_POLICY_KEYS:
        return dict(value, lead_destinations=[], home="", shop=False)
    return value


def settings(value=None):
    if value is None:
        return dict(destinations={}, npcs={})
    if not isinstance(value, dict) or set(value) != {"destinations", "npcs"}:
        raise ValueError("Invalid controlled actions")
    if (
        not isinstance(value["destinations"], dict)
        or len(value["destinations"]) > 100
        or not isinstance(value["npcs"], dict)
        or len(value["npcs"]) > 1000
    ):
        raise ValueError("Too many destinations or NPC permissions")
    points = {identifier(k): destination(v) for k, v in value["destinations"].items()}
    if any(k != v["id"] for k, v in points.items()):
        raise ValueError("Destination ID mismatch")
    return dict(
        destinations=points,
        npcs={
            identifier(k): policy(migrate_policy(v), points)
            for k, v in value["npcs"].items()
        },
    )


def choices(config, npc, world):
    p = config["npcs"].get(npc, DEFAULT_POLICY)
    if not p["enabled"]:
        return []
    return (
        [
            dict(
                id="walk:" + k,
                description="Walk to " + config["destinations"][k]["name"],
            )
            for k in p["destinations"]
            if config["destinations"][k]["world"] == world
        ]
        + [
            dict(
                id="lead:" + k,
                description="Lead the speaking player to "
                + config["destinations"][k]["name"]
                + ", waiting if they fall behind",
            )
            for k in p["lead_destinations"]
            if config["destinations"][k]["world"] == world
        ]
        + (
            [
                dict(
                    id="home:" + p["home"],
                    description="Return to home: "
                    + config["destinations"][p["home"]]["name"],
                )
            ]
            if p["home"] and config["destinations"][p["home"]]["world"] == world
            else []
        )
        + (
            [
                dict(
                    id="shop:open",
                    description="Open my weapons shop for the speaking player",
                ),
                dict(
                    id="shop:haggle",
                    description="On an explicit request to bargain or get a better price, ask the game to roll against the configured success percentage and open the shop with the resulting personal prices. Never claim a result before the roll. Repeated requests reuse the result for the configured cooldown.",
                ),
            ]
            if p["shop"]
            else []
        )
        + [dict(id="gesture:" + k, description=k.title()) for k in p["gestures"]]
    )


def parse_reply(raw, allowed):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("Action response must be JSON")
    if (
        not isinstance(value, dict)
        or set(value) != {"speech", "action"}
        or not isinstance(value["speech"], str)
        or not value["speech"].strip()
        or not isinstance(value["action"], str)
    ):
        raise ValueError("Invalid action response")
    if value["action"] and value["action"] not in {v["id"] for v in allowed}:
        raise ValueError("Unapproved action choice")
    return value["speech"], value["action"]
