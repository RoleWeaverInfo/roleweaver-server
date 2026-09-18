"""Validated merchant rules and a curated native item catalogue."""

import re
import hashlib
import json
from pathlib import Path
from .actions import identifier

DEFAULT_RULES = dict(enabled=True, chance=50, discount=5, cooldown=600)
CATALOG = json.loads(
    Path(__file__).with_name("merchant_catalog.json").read_text(encoding="utf-8")
)


def rules(value):
    if (
        not isinstance(value, dict)
        or set(value) != set(DEFAULT_RULES)
        or type(value["enabled"]) is not bool
    ):
        raise ValueError("Invalid haggle rules")
    for key, low, high in (
        ("chance", 0, 100),
        ("discount", 0, 10),
        ("cooldown", 60, 86400),
    ):
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
    return dict(value)


def configs(value=None):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 1000:
        raise ValueError("Invalid merchant settings")
    out = {}
    for npc, entry in value.items():
        identifier(npc)
        if (
            not isinstance(entry, dict)
            or set(entry) != {"rules", "revision"}
            or not isinstance(entry["revision"], str)
            or not re.fullmatch("[0-9a-f]{24}", entry["revision"])
        ):
            raise ValueError("Invalid merchant revision")
        value = entry["rules"]
        revision = entry["revision"]
        if isinstance(value, dict) and set(value) == {
            "enabled",
            "dc",
            "strong_dc",
            "discount",
            "strong_discount",
            "cooldown",
        }:
            if type(value["enabled"]) is not bool:
                raise ValueError("Invalid legacy haggle rules")
            for key, low, high in (
                ("dc", 1, 40),
                ("strong_dc", 1, 50),
                ("discount", 0, 10),
                ("strong_discount", 0, 10),
                ("cooldown", 60, 86400),
            ):
                if type(value[key]) is not int or not low <= value[key] <= high:
                    raise ValueError("Invalid legacy haggle rules")
            if (
                value["strong_dc"] < value["dc"]
                or value["strong_discount"] < value["discount"]
            ):
                raise ValueError("Invalid legacy haggle rules")
            value = dict(
                enabled=value["enabled"],
                chance=max(0, min(100, (21 - value["dc"]) * 5)),
                discount=value["discount"],
                cooldown=value["cooldown"],
            )
            revision = hashlib.sha256(("percent-v1:" + revision).encode()).hexdigest()[
                :24
            ]
        out[npc] = dict(rules=rules(value), revision=revision)
    return out


PRICE_LANGUAGE = re.compile(
    r"\b(price|prices|cost|costs|gold|coins?|gp|worth|how much)\b", re.I
)


def price_reply(text, speech, shop, action=""):
    """Price dialogue uses final game values, never model arithmetic or history."""
    if action == "shop:haggle":
        return "Let me see what price I can offer you.", False
    if not (PRICE_LANGUAGE.search(speech) or PRICE_LANGUAGE.search(text)):
        return text, False
    if not shop.get("available") or not shop.get("customer_quote"):
        return (
            "Let me check your current prices. Please ask me again in a moment.",
            False,
        )
    items = shop.get("items", [])
    words = set(re.findall(r"[a-z]+", speech.lower())) - {
        "the",
        "a",
        "of",
        "for",
        "is",
        "it",
        "what",
        "how",
        "much",
        "price",
        "cost",
        "gold",
        "me",
        "you",
        "can",
        "i",
        "to",
        "and",
    }
    matched = [
        i for i in items if any(w in i["name"].lower() for w in words if len(w) > 2)
    ]
    rows = []
    for item in matched or items:
        value = (item["name"], item["price"])
        if value not in rows:
            rows.append(value)
    if not rows:
        return "I have no stock to quote at the moment.", True
    parts = []
    for name, price in rows:
        entry = f"{name}: {price} gold"
        if sum(len(x) + 2 for x in parts) + len(entry) > 650:
            break
        parts.append(entry)
    suffix = (
        ". Ask to browse the shop for the remaining goods."
        if len(parts) < len(rows)
        else "."
    )
    return "Your current prices are " + "; ".join(parts) + suffix, True
