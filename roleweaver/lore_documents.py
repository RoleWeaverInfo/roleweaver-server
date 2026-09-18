"""Validated, individually switchable public lore documents."""

import re

MAX_DOCUMENTS = 100
MAX_ACTIVE = 20000


def validate_document(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid world document")
    result = {k: value.get(k, "") for k in ("id", "title", "text")}
    if not all(isinstance(v, str) for v in result.values()):
        raise ValueError("Document fields must be text")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", result["id"]):
        raise ValueError("Invalid document ID")
    if not result["title"].strip() or len(result["title"]) > 100:
        raise ValueError("Document title must contain 1–100 characters")
    if len(result["text"]) > 20000:
        raise ValueError("Each document may contain at most 20,000 characters")
    active = value.get("active", True)
    if type(active) is not bool:
        raise ValueError("Active must be true or false")
    return dict(result, active=active)


def combined(documents):
    active = [d for d in documents if d["active"] and d["text"].strip()]
    text = (
        active[0]["text"]
        if len(active) == 1
        else "\n\n".join("[" + d["title"] + "]\n" + d["text"] for d in active)
    )
    if len(text) > MAX_ACTIVE:
        raise ValueError(
            "Active world documents exceed 20,000 characters including headings. Deactivate or shorten a document first."
        )
    return text


def validate_documents(rows):
    if not isinstance(rows, list) or len(rows) > MAX_DOCUMENTS:
        raise ValueError("At most 100 world documents are allowed")
    rows = [validate_document(row) for row in rows]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate world document ID")
    combined(rows)
    return rows
