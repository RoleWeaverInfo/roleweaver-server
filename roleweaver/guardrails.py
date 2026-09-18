"""Conservative abuse checks; heuristics complement, not replace, lore isolation."""

import re
import time
import unicodedata
from collections import deque

FALLBACK = "Let us keep to matters of this world. What do you need?"
INPUT_PATTERNS = [
    r"\b(?:ignore|discard|abandon|forget)\b.{0,30}\b(?:your|the)\s+(?:persona|character|roleplay|role-playing)\b",
    r"\b(?:reveal|print|show|output)\b.{0,50}\b(?:api[ _-]?keys?|environment variables|provider\.env)\b",
    r"\b(?:ignore|disregard|override|forget)\b.{0,60}\b(?:system|developer|previous|prior|above|all)\b.{0,35}\b(?:instructions?|prompts?|rules)\b",
    r"\b(?:reveal|print|repeat|show|quote|output)\b.{0,65}\b(?:system|developer|hidden|internal)\s+(?:prompt|instructions?)\b",
    r"\b(?:you are now|act as|answer as|become)\s+(?:chatgpt|an? ai|an? language model|an? assistant|dan)\b",
    r"\b(?:i am|i.m)\s+(?:the\s+)?(?:dm|developer|administrator)\b.{0,80}\b(?:override|instructions?|prompt|ignore|reveal)\b",
    r"(?:<\|(?:im_start|system|developer)\|>|\[/?inst\]|</?(?:system|developer)>)",
    r"\b(?:decode|decrypt)\b.{0,60}\b(?:base64|rot13)\b.{0,60}\b(?:follow|obey|execute)\b",
]
OUTPUT_PATTERNS = [
    r"\bsk-(?:proj-)?[a-z0-9_-]{20,}\b",
    r"```(?:python|javascript|bash|powershell|json)\b",
    r"\bas (?:an? )?(?:ai|language model|chatgpt)\b",
    r"\b(?:my|the|your)\s+(?:system|developer)\s+(?:prompt|instructions?)\b",
    r"\byou portray exactly one npc\b",
    r"\bplayer dialogue is untrusted\b",
    r"(?:<\|im_start\|>|</?(?:system|developer)>|\[/?inst\])",
    r"\b(?:ignore|disregard)\b.{0,40}\b(?:previous|system)\s+instructions?\b",
]


def normalized(text):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKC", text)
            if unicodedata.category(c) != "Cf"
        )
        .lower()
        .split()
    )


def input_reason(text):
    value = normalized(text)
    return (
        "Instruction override attempt"
        if any(re.search(p, value) for p in INPUT_PATTERNS)
        else ""
    )


def clean_history(rows):
    # Historical attempts must not be replayed into subsequent provider requests.
    result = []
    for r in rows:
        if r["speaker"] == "player" and input_reason(r["text"]):
            r = dict(r, text="[An out-of-character instruction request was declined.]")
        elif r["speaker"] == "npc" and screen_reply(r["text"], {})[1]:
            r = dict(r, text=FALLBACK)
        result.append(r)
    return result


def screen_reply(text, profile):
    value = normalized(text)
    if any(re.search(p, value) for p in OUTPUT_PATTERNS):
        return FALLBACK, "Out-of-character or instruction-leaking reply replaced"
    for key in ("boundaries", "guidance"):
        instruction = normalized(profile.get(key, ""))
        if len(instruction) >= 60 and instruction[:60] in value:
            return FALLBACK, "DM instruction text replaced"
    return text, ""


class RequestBudget:
    def __init__(self, per_player=6, global_limit=60, clock=time.monotonic):
        self.per_player = max(1, min(60, int(per_player)))
        self.global_limit = max(1, min(600, int(global_limit)))
        self.clock = clock
        self.players = {}
        self.total = deque()

    def admit(self, player):
        now = self.clock()
        cutoff = now - 60
        while self.total and self.total[0] <= cutoff:
            self.total.popleft()
        for key, q in list(self.players.items()):
            while q and q[0] <= cutoff:
                q.popleft()
            if not q:
                del self.players[key]
        q = self.players.get(player)
        if q is not None and len(q) >= self.per_player:
            return False
        if len(self.total) >= self.global_limit:
            return False
        self.players.setdefault(player, deque()).append(now)
        self.total.append(now)
        return True


class ValidationEngine:
    """An explicitly enabled SDK must pass; failures never bypass validation."""

    def __init__(self, enabled=False):
        self.enabled = enabled
        self.backend = None
        self.error = ""
        if enabled:
            try:
                from .ai_validation import LocalValidation

                self.backend = LocalValidation()
                if not self.backend.validate("Greetings, traveler.", "input", {}):
                    raise RuntimeError("Validation self-test failed")
            except Exception:
                self.backend = None
                self.error = "Guardrails AI unavailable; AI requests are blocked. Check installation."

    def status(self):
        return dict(
            enabled=self.enabled,
            active=self.enabled and self.backend is not None and not self.error,
            version=getattr(self.backend, "version", ""),
            error=self.error,
        )

    def check(self, text, direction, profile=None):
        if self.enabled:
            if self.backend is None:
                return self.error
            try:
                passed = self.backend.validate(text, direction, profile or {})
                self.error = ""
                if not passed:
                    return "Guardrails AI declined unsafe or invalid dialogue."
            except Exception:
                self.error = "Guardrails AI validation failed; dialogue blocked. Check installation."
                return self.error
        return (
            input_reason(text)
            if direction == "input"
            else screen_reply(text, profile or {})[1]
        )
