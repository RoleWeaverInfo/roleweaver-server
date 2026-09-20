"""Bounded, opt-in story capabilities supplied by trusted module scripts.

No player text is parsed as configuration. Native scripts recheck every proposed
transition; the model interprets narrative meaning, not reward authority.
"""

import json
import re


def context(value):
    if not isinstance(value, dict) or value.get("protocol") != 1:
        return {}
    if len(json.dumps(value)) > 16000:
        return {}
    if "visit" in value and (
        not isinstance(value["visit"], str) or not 1 <= len(value["visit"]) <= 100
    ):
        return {}
    token = value.get("token")
    choices = value.get("actions")
    if not isinstance(token, str) or not 1 <= len(token) <= 100:
        return {}
    if not isinstance(choices, list) or len(choices) > 40:
        return {}
    seen = set()
    for choice in choices:
        if not isinstance(choice, dict) or set(choice) != {"id", "description"}:
            return {}
        ident, description = choice["id"], choice["description"]
        if not isinstance(ident, str) or not re.fullmatch(
            r"story:[a-z0-9_]{1,48}", ident
        ):
            return {}
        if ident in seen or not isinstance(description, str) or len(description) > 1000:
            return {}
        seen.add(ident)
    return value


def facts(value):
    """Only this listener's authorized narrative facts go to the lore reviewer."""
    value = context(value)
    return {
        key: value[key]
        for key in (
            "appointed",
            "completed",
            "king_present",
            "own_testimony",
            "recorded_accounts",
        )
        if key in value
    }


def mark_history(rows, first_message):
    """Keep old dialogue as personal memory, labelled outside the current case."""
    if type(first_message) is not int:
        return rows
    return [dict(row, previous_visit=row.get("id", 0) < first_message) for row in rows]
