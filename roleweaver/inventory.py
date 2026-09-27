"""Finite game-owned inventory and DM-scoped tasks; never synthesize an item.

The model chooses an opaque action ID. Actual ownership, distance, equipment,
value limits and player consent are checked again by the native bridge.
"""

import re
import time
from . import perception

DEFAULT = dict(
    containers=[],
    take=False,
    deposit=False,
    give=False,
    receive=False,
    exchange=False,
    fetch=False,
    heal=False,
    equip=False,
    use_items=False,
    usable_resrefs=[],
    radius=40,
    max_value=100,
    barter_percent=100,
)
VERBS = (
    "inspect",
    "take",
    "deposit",
    "give",
    "fetch",
    "aid",
    "exchange",
    "swap",
    "equip",
    "unequip",
    "use",
)


def policy(value=None):
    if value is None:
        return dict(DEFAULT, containers=[], usable_resrefs=[])
    if isinstance(value, dict):
        value = (
            dict(equip=False, use_items=False, usable_resrefs=[], **value)
            if not ({"equip", "use_items", "usable_resrefs"} & set(value))
            else value
        )
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError("Invalid inventory permissions")
    for key in (
        "take",
        "deposit",
        "give",
        "receive",
        "exchange",
        "fetch",
        "heal",
        "equip",
        "use_items",
    ):
        if type(value[key]) is not bool:
            raise ValueError("Inventory permissions must be enabled or disabled")
    for key, low, high in (
        ("radius", 2, 40),
        ("max_value", 0, 100000),
        ("barter_percent", 25, 200),
    ):
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError(f"{key} must be {low}–{high}")
    refs = value["usable_resrefs"]
    if (
        not isinstance(refs, list)
        or len(refs) > 30
        or any(
            not isinstance(r, str) or not re.fullmatch(r"[a-z0-9_]{1,16}", r)
            for r in refs
        )
        or len(set(refs)) != len(refs)
    ):
        raise ValueError("Choose up to 30 unique lowercase item blueprint resrefs")
    tags = value["containers"]
    if (
        not isinstance(tags, list)
        or len(tags) > 30
        or any(
            not isinstance(x, str) or not x or len(x) > 128 or not x.isprintable()
            for x in tags
        )
        or len(set(tags)) != len(tags)
    ):
        raise ValueError("Choose up to 30 unique container tags")
    return dict(value, containers=list(tags))


def items(raw):
    result = []
    if not isinstance(raw, list):
        return result
    for row in raw[:32]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("ref"), str)
            or not re.fullmatch(r"i[1-9][0-9]{0,9}", row["ref"])
        ):
            continue
        if type(row.get("quantity")) is not int or not 1 <= row["quantity"] <= 99999:
            continue
        result.append(
            dict(
                ref=row["ref"],
                name=perception.label(row.get("name", "Item")),
                quantity=row["quantity"],
                healing=row.get("healing") == 1,
                healing_kind=(
                    row.get("healing_kind")
                    if row.get("healing_kind") in ("potion", "bandage")
                    else "potion"
                ),
                equipped=row.get("equipped") == 1,
                slots=[
                    n for n in row.get("slots", []) if type(n) is int and 0 <= n < 14
                ][:14],
                uses=[
                    dict(
                        index=u["index"],
                        name=perception.label(u.get("name", "Item power")),
                    )
                    for u in row.get("uses", [])[:16]
                    if isinstance(u, dict)
                    and type(u.get("index")) is int
                    and 0 <= u["index"] < 64
                ],
                stackable=row.get("stackable") != 0,
            )
        )
    return result


def snapshot(state):
    raw = state.get("inventory", {})
    if (
        not isinstance(raw, dict)
        or state.get("inventory_protocol") != 1
        or time.monotonic() - state.get("seen", 0) >= 4
    ):
        return dict(available=False, items=[], containers=[])
    containers = []
    for c in (
        raw.get("containers", []) if isinstance(raw.get("containers", []), list) else []
    )[:8]:
        if (
            isinstance(c, dict)
            and isinstance(c.get("ref"), str)
            and re.fullmatch(r"v[1-9][0-9]{0,9}", c["ref"])
        ):
            containers.append(
                dict(
                    ref=c["ref"],
                    name=perception.label(c.get("name", "Container")),
                    items=items(c.get("items", [])),
                )
            )
    return dict(
        available=True,
        items=items(raw.get("items", [])),
        containers=containers,
        note="Only eligible, identified items within DM limits are listed. Omission is not proof of an empty inventory. Container contents appear only after a successful inspection.",
    )


def choices(saved, state, listener, can_receive, peer_items=lambda peer: []):
    p = saved.get("inventory", DEFAULT)
    view = snapshot(state)
    if not saved.get("enabled") or not view["available"]:
        return []
    out = []

    def add(verb, target, label):
        out.append(dict(id=verb + ":" + target, description=label))

    targets = state.get("nearby_targets", {})
    containers = {
        r: o
        for r, o in targets.items()
        if o["kind"] == "container"
        and o.get("tag") in p["containers"]
        and o["distance"] <= p["radius"]
    }
    peers = {
        r: o
        for r, o in targets.items()
        if o.get("peer") and o["distance"] <= p["radius"] and can_receive(o["peer"])
    }
    recipients = {"player": dict(label="the requesting player")} if listener else {}
    recipients.update(peers)
    for ref, c in list(containers.items())[:8]:
        add("inspect", ref, "Walk to, open and inspect " + c["label"])
        if p["deposit"]:
            for item in view["items"][:16]:
                if item["equipped"]:
                    continue
                add(
                    "deposit",
                    ref + ":" + item["ref"],
                    f'Put {item["quantity"]} x {item["name"]} into {c["label"]}',
                )
    slot_names = [
        "head",
        "chest",
        "boots",
        "arms",
        "right hand",
        "left hand",
        "cloak",
        "left ring",
        "right ring",
        "neck",
        "belt",
        "arrows",
        "bullets",
        "bolts",
    ]
    for item in view["items"][:16]:
        if p.get("equip"):
            if item["equipped"]:
                add("unequip", "self:" + item["ref"], "Unequip " + item["name"])
            else:
                for slot in item["slots"]:
                    add(
                        "equip",
                        "self:" + item["ref"] + ":" + str(slot),
                        "Equip "
                        + item["name"]
                        + " in "
                        + slot_names[slot]
                        + "; normal game restrictions apply",
                    )
        if p.get("use_items"):
            for use in item["uses"]:
                add(
                    "use",
                    "self:" + item["ref"] + ":" + str(use["index"]),
                    "Use "
                    + item["name"]
                    + ": "
                    + use["name"]
                    + " on yourself; consumes normal charges",
                )
        if item["equipped"]:
            continue
        for ref, who in list(recipients.items())[:8]:
            if p["give"]:
                add(
                    "give",
                    ref + ":" + item["ref"],
                    f'Deliver {item["quantity"]} x {item["name"]} to {who["label"]}',
                )
            if p["heal"] and item["healing"]:
                add(
                    "aid",
                    ref + ":" + item["ref"],
                    f'Use carried {item["name"]} to help {who["label"]}; healing kits use the game Heal skill check',
                )
        if p["heal"] and item["healing"]:
            add(
                "aid",
                "self:" + item["ref"],
                f'Use carried {item["name"]} to treat your own injuries; kits use the game Heal skill check',
            )
    for c in view["containers"]:
        if c["ref"] not in containers:
            continue
        for item in c["items"][:16]:
            if p["take"]:
                add(
                    "take",
                    c["ref"] + ":" + item["ref"],
                    f'Take {item["quantity"]} x {item["name"]} from {c["name"]}',
                )
            if p["fetch"] and p["take"] and p["give"] and not item["stackable"]:
                for ref, who in list(recipients.items())[:8]:
                    add(
                        "fetch",
                        c["ref"] + ":" + item["ref"] + ":" + ref,
                        f'Fetch {item["quantity"]} x {item["name"]} from {c["name"]} and deliver to {who["label"]}',
                    )
    if p["exchange"] and p["receive"]:
        for ref, who in list(peers.items())[:4]:
            for own in view["items"][:8]:
                if own["equipped"] or own["stackable"] or own["quantity"] != 1:
                    continue
                for offer in peer_items(who["peer"])[:8]:
                    if (
                        not offer.get("equipped")
                        and not offer["stackable"]
                        and offer["quantity"] == 1
                    ):
                        add(
                            "swap",
                            ref + ":" + own["ref"] + ":" + offer["ref"],
                            f'Offer {own["name"]} to {who["label"]} in exchange for their {offer["name"]}; both DM value rules must pass.',
                        )
    if listener and (p["exchange"] or p["give"] or p["receive"]):
        # Always retain the consent window choice even in a crowded scene.
        out.insert(
            0,
            dict(
                id="exchange:player",
                description="Open the item exchange window for the requesting player; they select and confirm giving, receiving or a fair barter. No transfer until confirmation.",
            ),
        )
    return out[:256]
