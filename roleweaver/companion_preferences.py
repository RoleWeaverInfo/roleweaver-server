"""Validation and model projection of player settings stored by the service.

The finite tone choices influence delivery, not the character's identity, lore or
server limits. Malformed preference messages never enable extra actions.
"""

import re

DEFAULT = dict(
    version=1,
    reply=1,
    tone=0,
    followups=1,
    movement=1,
    inventory=1,
    collect=1,
    deliver=1,
)
LIMITS = dict(
    version=1,
    reply=2,
    tone=4,
    followups=1,
    movement=1,
    inventory=1,
    collect=1,
    deliver=1,
)
TONES = (
    "Keep your established personality and speaking style.",
    "Use a warmer delivery while preserving your established personality.",
    "Use a little playful humour where appropriate to the situation and your personality.",
    "Use a reserved, understated delivery consistent with your personality.",
    "Use a serious, focused delivery consistent with your personality.",
)
LENGTHS = (
    "Be brief: one short sentence, usually no more than 30 words.",
    "Be natural and concise: one or two short sentences, usually no more than 70 words.",
    "Give a little more detail when helpful, usually no more than 110 words.",
)
CAPS = (240, 600, 900)


def validate(raw):
    if (
        not isinstance(raw, dict)
        or set(raw) != set(DEFAULT)
        or any(type(raw[k]) is not int or not 0 <= raw[k] <= LIMITS[k] for k in DEFAULT)
        or raw["version"] != 1
    ):
        raise ValueError("Invalid companion preferences")
    return dict(raw)


def records(raw):
    if not isinstance(raw, dict) or len(raw) > 1000:
        raise ValueError("Invalid companion preference records")
    if any(
        not isinstance(k, str) or not re.fullmatch(r"cp_[a-f0-9]{21}", k) for k in raw
    ):
        raise ValueError("Invalid companion preference identity")
    return {key: validate(value) for key, value in raw.items()}


def settings(event):
    if "companion_preferences_protocol" not in event:
        return dict(DEFAULT)  # Compatible with the earlier companion bridge.
    raw = event.get("companion_preferences")
    if (
        type(event.get("companion_preferences_protocol")) is int
        and event["companion_preferences_protocol"] == 1
        and isinstance(raw, dict)
        and set(raw) == set(DEFAULT)
        and all(type(raw[k]) is int and 0 <= raw[k] <= LIMITS[k] for k in DEFAULT)
        and raw["version"] == 1
    ):
        return dict(raw)
    return dict(DEFAULT, followups=0, movement=0, inventory=0, collect=0, deliver=0)


def voice(original, preference):
    return "\n".join(
        (
            original,
            "Player's delivery preference: " + LENGTHS[preference["reply"]],
            TONES[preference["tone"]],
            "These preferences do not change your history, memories, lore, loyalties or boundaries. Server/DM character constraints still apply.",
        )
    )


def limit_reply(text, preference):
    limit = CAPS[preference["reply"]]
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
