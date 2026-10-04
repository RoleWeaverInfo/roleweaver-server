"""Bounded public speech observed by a familiar, used only for its current reply.

The game checks audibility and opt-in when speech occurs. This boundary also
checks freshness, settings and payload shape before passing testimony to a model.
It never schedules replies, persists a transcript, or grants action permissions.
"""

import time

from . import companion_preferences, perception

MAX_LINES = 8
MAX_AGE = 120
MAX_TEXT = 400


def context(event, config, now=None):
    now = time.monotonic() if now is None else now
    empty = dict(enabled=False, lines=[])
    if (
        config.get("companion_listening_enabled", True) is not True
        or not companion_preferences.settings(event)["listening"]
        or type(event.get("hearing_protocol")) is not int
        or event["hearing_protocol"] != 1
        or event.get("hearing_enabled") != 1
        or not 0 <= now - event.get("seen", 0) < 4
    ):
        return empty
    tick = event.get("tick")
    rows = event.get("heard_speech")
    if type(tick) is not int or not isinstance(rows, list):
        return empty
    lines = []
    for row in rows[-MAX_LINES:]:
        if not isinstance(row, dict):
            continue
        when, text = row.get("tick"), row.get("text")
        speaker_kind = row.get("speaker_kind")
        if (
            type(when) is not int
            or not 0 <= tick - when <= MAX_AGE
            or row.get("channel") != "talk"
            or speaker_kind not in ("owner", "player", "npc")
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > MAX_TEXT
            or text.lstrip().startswith(("/", "((", "!"))
        ):
            continue
        speaker = "Your owner" if speaker_kind == "owner" else "Unidentified traveler"
        if speaker_kind == "npc":
            speaker = perception.label(row.get("speaker", "Nearby creature"))
        lines.append(
            dict(
                speaker=speaker,
                speaker_kind=speaker_kind,
                appearance=perception.label(row.get("appearance", "")),
                text="".join(c for c in text if c.isprintable() or c == "\n"),
                seconds_ago=tick - when,
            )
        )
    return dict(enabled=True, lines=lines, max_age_seconds=MAX_AGE)
