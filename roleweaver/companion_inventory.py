"""Familiar cargo context; game code owns items, targets, consent and persistence.

Only a bounded list of offered action IDs crosses into the model. Object handles,
satchel ownership, native snapshots and character saves stay outside AI storage.
"""

import re
import time

from . import inventory, perception

DEFAULT = dict(enabled=True, radius=20, max_value=10000, containers=[])


def policy(value=None):
    if value is None:
        return dict(DEFAULT, containers=[])
    if not isinstance(value, dict) or set(value) - set(DEFAULT):
        raise ValueError("Invalid companion inventory settings")
    result = dict(DEFAULT, **value)
    if type(result["enabled"]) is not bool:
        raise ValueError("Companion inventory enabled must be true or false")
    for field, low, high in (("radius", 3, 40), ("max_value", 0, 100000)):
        if type(result[field]) is not int or not low <= result[field] <= high:
            raise ValueError(f"Companion inventory {field} must be {low}–{high}")
    tags = result["containers"]
    if (
        not isinstance(tags, list)
        or len(tags) > 30
        or any(
            not isinstance(tag, str)
            or not tag
            or len(tag) > 128
            or not tag.isprintable()
            for tag in tags
        )
        or len(set(tags)) != len(tags)
    ):
        raise ValueError("Choose up to 30 distinct approved container tags")
    return dict(result, containers=list(tags))


def configured(config):
    try:
        return policy(config.get("companion_inventory"))
    except ValueError:
        # A mistyped permission must not turn on broader access or stop chat.
        return dict(DEFAULT, enabled=False, containers=[])


def context(event, config):
    empty = dict(available=False, items=[], containers=[], ground=[])
    raw = event.get("companion_inventory")
    if (
        not configured(config)["enabled"]
        or event.get("companion_inventory_protocol") != 1
        or not isinstance(raw, dict)
        or raw.get("available") != 1
        or time.monotonic() - event.get("seen", 0) >= 4
    ):
        return empty, []
    choices, seen = [], set()
    candidates = raw.get("choices", [])
    for row in candidates[:96] if isinstance(candidates, list) else []:
        if not isinstance(row, dict):
            continue
        key, description = row.get("id"), row.get("description")
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"cpinv:(?:[0-9]|[1-8][0-9]|9[0-5])", key)
            or key in seen
            or not isinstance(description, str)
            or not description.strip()
        ):
            continue
        seen.add(key)
        choices.append(
            dict(
                id=key,
                description="".join(c for c in description[:240] if c.isprintable()),
            )
        )
    boxes = raw.get("containers", [])
    boxes = boxes[:8] if isinstance(boxes, list) else []
    return (
        dict(
            available=True,
            items=inventory.items(raw.get("items")),
            ground=inventory.items(raw.get("ground")),
            containers=[
                dict(
                    name=perception.label(box.get("name", "Container")),
                    items=inventory.items(box.get("items")),
                )
                for box in boxes
                if isinstance(box, dict)
            ],
            status="".join(
                c for c in str(raw.get("status", ""))[:240] if c.isprintable()
            ),
            note="Your working inventory is your owner's familiar satchel. Only eligible items are listed; unseen contents remain unknown. Use only currently offered actions. Pickup and delivery require physically reaching the target. Other players must accept deliveries. Never claim a transfer completed before game confirmation. Player inventories are private; only their confirmed offers become yours.",
        ),
        choices,
    )
