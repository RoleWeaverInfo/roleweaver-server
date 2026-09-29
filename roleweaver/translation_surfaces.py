"""Bounded requests for native dialogue text and private hover labels.

Only the game supplies these records. The provider translates text; it never
selects a dialogue branch, target object, custom-token number or game action.
"""

import re


def name_context(resref, object_type, mode):
    context = str(resref)[:16] + ":" + str(object_type)
    return context + (":label" if mode == "translate" else "")


def lookup_batch(cache, event, preference, active):
    dialogue = event["kind"] == "translation_dialogue"
    rows = event.get("texts")
    if not isinstance(rows, list) or not 1 <= len(rows) <= (32 if dialogue else 16):
        raise ValueError("Invalid translation batch")
    resource = event.get("dialogue", "")
    if dialogue and (
        not isinstance(resource, str) or not re.fullmatch(r"[a-z0-9_]{1,16}", resource)
    ):
        raise ValueError("Invalid dialogue resource")
    result, seen = [], set()
    # Validate the complete batch before submitting any work.
    validated = []
    for row in rows:
        if not isinstance(row, dict) or row.get("approved") != 1:
            raise ValueError("Unapproved translation source")
        original = row.get("text")
        if not isinstance(original, str) or not 1 <= len(original) <= (
            2000 if dialogue else 200
        ):
            raise ValueError("Invalid translation text")
        if dialogue:
            key, kind = row.get("id"), row.get("kind")
            if (
                type(key) is not int
                or not 0 <= key < 10000
                or kind not in ("dialogue_entry", "dialogue_reply")
            ):
                raise ValueError("Invalid dialogue node")
            if event.get("on_demand") == 1 and (
                len(rows) != 1
                or type(row.get("display_token")) is not int
                or not 100000 <= row["display_token"] <= 2147483647
            ):
                raise ValueError("Invalid on-demand dialogue token")
            slot = "dialogue:" + resource + ":" + kind + ":" + str(key)
            context, mode = "dialogue:" + resource, "auto"
            key = (kind, key)
        else:
            key, kind = row.get("object"), "name"
            # ObjectToString on the native server emits unpadded hex (e.g. "3"
            # or "e"). Accept both forms; keep the wire spelling for the reply.
            if not isinstance(key, str) or not re.fullmatch(r"[0-9a-fA-F]{1,8}", key):
                raise ValueError("Invalid name object")
            object_id = int(key, 16)
            if object_id == 0x7F000000:
                raise ValueError("Invalid name object")
            if (
                row.get("object_type") not in (1, 64)
                or row.get("player_character") != 0
            ):
                raise ValueError("Player or unsupported hover name")
            mode = row.get("name_mode", "auto")
            if mode not in ("auto", "preserve", "translate"):
                raise ValueError("Invalid name policy")
            slot = event["session"] + ":" + format(object_id, "x") + ":name"
            context = name_context(row.get("resref", ""), row["object_type"], mode)
            key = object_id
        if key in seen:
            raise ValueError("Duplicate translation source")
        seen.add(key)
        validated.append((row, slot, kind, original, context, mode))
    for row, slot, kind, original, context, mode in validated:
        translated = (
            cache.lookup(slot, preference["language"], kind, original, context)
            if active and mode != "preserve"
            else None
        )
        result.append(dict(row, translated=translated or ""))
    return result
