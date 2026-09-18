"""Owner-configurable dialogue policy and local privacy masking."""

import copy
import json
import math
import re
import unicodedata

CATEGORIES = ("profanity", "hate", "violence", "sensitive")
THRESHOLDS = {"low": 0.9, "medium": 0.65, "high": 0.35}
DEFAULTS = {
    "levels": {key: "off" for key in CATEGORIES},
    "topics": "Real-world politics\nSexual content\nSelf-harm",
    "action": "fallback",
    "lore_check": False,
    "privacy": {"cards": True, "phones": True, "addresses": True},
}


def settings(value=None):
    if value is None:
        return copy.deepcopy(DEFAULTS)
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Invalid safeguard settings")
    result = copy.deepcopy(value)
    if not isinstance(result["levels"], dict) or set(result["levels"]) != set(
        CATEGORIES
    ):
        raise ValueError("Choose a sensitivity for each category")
    if any(v not in ("off", *THRESHOLDS) for v in result["levels"].values()):
        raise ValueError("Sensitivity must be Off, Low, Medium or High")
    if result["action"] not in ("log", "fallback", "block"):
        raise ValueError("Choose Log only, Fallback reply or Block reply")
    if type(result["lore_check"]) is not bool:
        raise ValueError("Invalid lore-check setting")
    if not isinstance(result["topics"], str) or len(result["topics"]) > 1000:
        raise ValueError("Sensitive topics must be at most 1,000 characters")
    result["topics"] = result["topics"].strip()
    if result["levels"]["sensitive"] != "off" and not result["topics"]:
        raise ValueError("Describe at least one sensitive topic")
    if (
        not isinstance(result["privacy"], dict)
        or set(result["privacy"]) != {"cards", "phones", "addresses"}
        or any(type(v) is not bool for v in result["privacy"].values())
    ):
        raise ValueError("Invalid privacy settings")
    return result


def needs_review(policy, direction):
    return any(v != "off" for v in policy["levels"].values()) or (
        direction == "output" and policy["lore_check"]
    )


def luhn(number):
    digits = [int(c) for c in number if c.isdecimal()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    return (
        sum(
            (d * 2 - 9 if d * 2 > 9 else d * 2) if i % 2 else d
            for i, d in enumerate(reversed(digits))
        )
        % 10
        == 0
    )


CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?![ -]?\d)")
PHONE = re.compile(
    r"(?<![\w\d])(?:\+\d{1,3}[ .-]?(?:\(?\d{1,4}\)?[ .-]?){2,5}\d{2,4}|(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}|\(\d{3}\)\s*\d{3}[ .-]?\d{4})(?!\d)"
)
ADDRESS = re.compile(
    r"\b\d{1,6}[A-Za-z]?\s+(?:[\w\x27.-]+\s+){1,5}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Way|Place|Pl|Terrace|Close)\b\.?"
    r"(?:[ ,]+(?:Apt|Apartment|Unit|Suite|Flat|#)\s*[\w-]+)?",
    re.I,
)


def scrub(text, policy):
    """Conservative format recognition, not universal PII detection or erasure."""
    if not any(policy["privacy"].values()):
        return text, []
    text = "".join(
        c
        for c in unicodedata.normalize("NFKC", text)
        if unicodedata.category(c) != "Cf"
    )
    found = []

    def replace(pattern, category, eligible=lambda _: True):
        nonlocal text

        def mask(match):
            if not eligible(match.group()):
                return match.group()
            found.append(category)
            return "[PRIVATE " + category.upper() + "]"

        text = pattern.sub(mask, text)

    if policy["privacy"]["cards"]:
        replace(CARD, "card", luhn)
    if policy["privacy"]["phones"]:
        replace(PHONE, "phone", lambda s: 10 <= sum(c.isdecimal() for c in s) <= 15)
        # Bare numbers require a phone label, to avoid treating game IDs as phones.
        text = re.sub(
            r"(?i)\b(phone|mobile|telephone|call me at)\s*[:=]?\s*(\d{10,15})\b",
            lambda m: (found.append("phone") or m[1] + " [PRIVATE PHONE]"),
            text,
        )
    if policy["privacy"]["addresses"]:
        replace(ADDRESS, "address")
    return text, sorted(set(found))


def scrub_tree(value, policy):
    if isinstance(value, str):
        return scrub(value, policy)[0]
    if isinstance(value, list):
        return [scrub_tree(v, policy) for v in value]
    if isinstance(value, dict):
        return {k: scrub_tree(v, policy) for k, v in value.items()}
    return value


def trusted_sources(profile, memories):
    # Only fields already authorized for this NPC. Never retrieve all lore here.
    return {
        "npc": {
            "name": profile.get("name", ""),
            "role": profile.get("role", ""),
            "lore": profile.get("lore", ""),
        },
        "world_lore": profile.get("world_lore", ""),
        "authorized_lore": profile.get("access_lore", []),
        "dm_memories": [m["text"] for m in memories],
        "live_shop": profile.get("merchant", {}),
    }


def parse_review(raw):
    """Reject malformed/partial reviewer responses instead of guessing a verdict."""
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"scores", "lore"}:
        raise ValueError("Invalid review response")
    scores = data["scores"]
    if not isinstance(scores, dict) or set(scores) != set(CATEGORIES):
        raise ValueError("Invalid review categories")
    for score in scores.values():
        if (
            type(score) not in (int, float)
            or not math.isfinite(score)
            or not 0 <= score <= 1
        ):
            raise ValueError("Invalid review score")
    if data["lore"] not in (
        "supported",
        "contradicted",
        "unsupported",
        "not_applicable",
    ):
        raise ValueError("Invalid lore verdict")
    return data


def flags(report, policy, direction):
    found = [
        key
        for key in CATEGORIES
        if policy["levels"][key] != "off"
        and report["scores"][key] >= THRESHOLDS[policy["levels"][key]]
    ]
    if (
        direction == "output"
        and policy["lore_check"]
        and report["lore"] in ("contradicted", "unsupported")
    ):
        found.append("lore_" + report["lore"])
    return found
