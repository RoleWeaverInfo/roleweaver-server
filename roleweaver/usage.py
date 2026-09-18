"""Bounded, content-free provider telemetry. Prices are owner-entered USD per million tokens."""

from contextlib import closing
import hashlib
import json
import math
import sqlite3
import threading
import time

WINDOWS = {
    "1h": (3600, 60),
    "24h": (86400, 1800),
    "7d": (604800, 10800),
    "30d": (2592000, 43200),
}


def tokens(value):
    return value if type(value) is int and 0 <= value <= 1000000000 else None


def counts(data):
    u = data.get("usage") if isinstance(data, dict) else None
    u = u if isinstance(u, dict) else {}
    incoming = tokens(u.get("prompt_tokens", u.get("input_tokens")))
    outgoing = tokens(u.get("completion_tokens", u.get("output_tokens")))
    details = u.get("prompt_tokens_details", u.get("input_tokens_details")) or {}
    cached = tokens(details.get("cached_tokens")) if isinstance(details, dict) else None
    details = u.get("completion_tokens_details", u.get("output_tokens_details")) or {}
    reasoning = (
        tokens(details.get("reasoning_tokens")) if isinstance(details, dict) else None
    )
    if cached is not None and (incoming is None or cached > incoming):
        cached = None
    if reasoning is not None and (outgoing is None or reasoning > outgoing):
        reasoning = None
    return dict(
        input_tokens=incoming,
        output_tokens=outgoing,
        cached_tokens=cached,
        reasoning_tokens=reasoning,
    )


def price(value):
    if not isinstance(value, dict):
        raise ValueError("Supply model pricing")
    result = {}
    for key in ("input", "output", "cached"):
        raw = value.get(key)
        if raw is None and key == "cached":
            result[key] = None
            continue
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(raw)
            or not 0 <= raw <= 10000
        ):
            raise ValueError(
                "Rates must be finite USD amounts between 0 and 10000 per million tokens"
            )
        result[key] = float(raw)
    ceiling = value.get("max_input_tokens")
    if ceiling is not None and (
        type(ceiling) is not int or not 1 <= ceiling <= 1000000000
    ):
        raise ValueError("Optional input-token ceiling must be a positive integer")
    result["max_input_tokens"] = ceiling
    return result


def estimate(c, rates):
    if not rates or c["input_tokens"] is None or c["output_tokens"] is None:
        return None
    if rates.get("max_input_tokens") and c["input_tokens"] > rates["max_input_tokens"]:
        return None
    cached = c["cached_tokens"] or 0
    rate = rates["cached"] if rates["cached"] is not None else rates["input"]
    return (
        (c["input_tokens"] - cached) * rates["input"]
        + cached * rate
        + c["output_tokens"] * rates["output"]
    ) / 1000000


def average(values):
    return sum(values) / len(values) if values else None


def percentile(values):
    return sorted(values)[max(0, math.ceil(len(values) * 0.95) - 1)] if values else None


class Usage:
    def __init__(self, path, config):
        self.path, self.lock, self.error = path, threading.RLock(), ""
        self.configure(config)
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS requests (
              id INTEGER PRIMARY KEY, created REAL NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
              npc TEXT NOT NULL, phase TEXT NOT NULL, duration_ms REAL NOT NULL, request_bytes INTEGER NOT NULL,
              request_chars INTEGER NOT NULL, response_bytes INTEGER NOT NULL, status TEXT NOT NULL,
              error TEXT NOT NULL, http_status INTEGER, input_tokens INTEGER, output_tokens INTEGER,
              cached_tokens INTEGER, reasoning_tokens INTEGER, cost_usd REAL, rates TEXT);
            CREATE INDEX IF NOT EXISTS request_time ON requests(created);
            CREATE TABLE IF NOT EXISTS prices (provider TEXT NOT NULL, model TEXT NOT NULL, rates TEXT NOT NULL,
              PRIMARY KEY(provider,model));
            """)

    def settings(self):
        with self.lock, closing(sqlite3.connect(self.path)) as db:
            return {
                r[0]: json.loads(r[1])
                for r in db.execute(
                    "SELECT model,rates FROM prices WHERE provider=? ORDER BY model",
                    (self.provider,),
                )
            }

    def save_price(self, model, value):
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise ValueError("Enter a model name, up to 128 characters")
        rates = price(value)
        with self.lock, closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO prices VALUES (?,?,?)",
                (self.provider, model, json.dumps(rates)),
            )
        return rates

    def configure(self, config):
        with self.lock:
            self.provider = hashlib.sha256(
                config.get("base_url", config.get("provider", "")).rstrip("/").encode()
            ).hexdigest()[:24]
            self.model = str(config.get("model", ""))[:128]

    def recorder(self, npc, phase, config=None):
        # Snapshot rates at request start: later edits never rewrite old estimates.
        provider_id = (
            hashlib.sha256(
                config.get("base_url", config.get("provider", "")).rstrip("/").encode()
            ).hexdigest()[:24]
            if config
            else self.provider
        )
        model = str(config.get("model", ""))[:128] if config else self.model
        try:
            with self.lock, closing(sqlite3.connect(self.path)) as db:
                rates_by_model = {
                    row[0]: json.loads(row[1])
                    for row in db.execute(
                        "SELECT model,rates FROM prices WHERE provider=?",
                        (provider_id,),
                    )
                }
        except Exception:
            rates_by_model = {}
            self.error = "Usage pricing could not be read."

        def record(event):
            try:
                actual_model = event.get("model") or model
                rates = rates_by_model.get(actual_model)
                c = counts(event.pop("data", {}))
                row = dict(
                    created=event["created"],
                    provider=provider_id,
                    model=actual_model,
                    npc=npc,
                    phase=phase,
                    **{
                        k: event[k]
                        for k in (
                            "duration_ms",
                            "request_bytes",
                            "request_chars",
                            "response_bytes",
                            "status",
                            "error",
                            "http_status",
                        )
                    },
                    **c,
                    cost_usd=estimate(c, rates),
                    rates=json.dumps(rates) if rates else None,
                )
                with self.lock, closing(sqlite3.connect(self.path)) as db, db:
                    db.execute(
                        "INSERT INTO requests("
                        + ",".join(row)
                        + ") VALUES ("
                        + ",".join("?" for _ in row)
                        + ")",
                        tuple(row.values()),
                    )
                    db.execute(
                        "DELETE FROM requests WHERE created<?", (time.time() - 2592000,)
                    )
                    db.execute(
                        "DELETE FROM requests WHERE id <= COALESCE((SELECT id FROM requests ORDER BY id DESC LIMIT 1 OFFSET 50000),-1)"
                    )
            except Exception:
                self.error = (
                    "Some usage records could not be saved. Totals may be incomplete."
                )

        return record

    def report(self, window="24h", npc="", phase="", model=""):
        if window not in WINDOWS:
            raise ValueError("Choose 1h, 24h, 7d or 30d")
        if phase not in (
            "",
            "dialogue",
            "input_review",
            "output_review",
            "connection_test",
        ):
            raise ValueError("Invalid request category")
        now = time.time()
        duration, step = WINDOWS[window]
        start = now - duration
        query = "SELECT * FROM requests WHERE created>=? AND created<=?"
        args = [start, now]
        for field, value in (("npc", npc), ("phase", phase), ("model", model)):
            if value:
                query += " AND " + field + "=?"
                args.append(value)
        with self.lock, closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM requests WHERE created<?", (now - 2592000,))
            db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute(query + " ORDER BY created,id", args)]
            choices = {
                key: [
                    r[0]
                    for r in db.execute(
                        "SELECT DISTINCT " + key + " FROM requests ORDER BY " + key
                    )
                ]
                for key in ("npc", "model")
            }
            earliest = db.execute("SELECT MIN(created) FROM requests").fetchone()[0]

        def summarize(group):
            known = [
                r
                for r in group
                if r["input_tokens"] is not None and r["output_tokens"] is not None
            ]
            priced = [r for r in group if r["cost_usd"] is not None]
            return dict(
                requests=len(group),
                errors=sum(r["status"] == "error" for r in group),
                token_requests=len(known),
                priced_requests=len(priced),
                input_reporting=sum(r["input_tokens"] is not None for r in group),
                output_reporting=sum(r["output_tokens"] is not None for r in group),
                input_tokens=sum(
                    r["input_tokens"] for r in group if r["input_tokens"] is not None
                ),
                output_tokens=sum(
                    r["output_tokens"] for r in group if r["output_tokens"] is not None
                ),
                cached_tokens=sum(r["cached_tokens"] or 0 for r in group),
                reasoning_tokens=sum(r["reasoning_tokens"] or 0 for r in group),
                cost_usd=sum(r["cost_usd"] for r in priced) if priced else None,
                average_ms=average([r["duration_ms"] for r in group]),
                p95_ms=percentile([r["duration_ms"] for r in group]),
                average_bytes=average([r["request_bytes"] for r in group]),
                max_bytes=max([r["request_bytes"] for r in group], default=None),
                total_request_bytes=sum(r["request_bytes"] for r in group),
            )

        bins = [[] for _ in range(math.ceil(duration / step))]
        for row in rows:
            bins[min(len(bins) - 1, int((row["created"] - start) // step))].append(row)
        series = [
            dict(time=start + i * step, **summarize(group))
            for i, group in enumerate(bins)
        ]
        grouped = {}
        for row in rows:
            grouped.setdefault((row["npc"], row["model"], row["phase"]), []).append(row)
        breakdown = [
            dict(npc=k[0], model=k[1], phase=k[2], **summarize(g))
            for k, g in grouped.items()
        ]
        recent = [
            {k: v for k, v in r.items() if k not in ("provider", "rates")}
            for r in reversed(rows[-50:])
        ]
        return dict(
            summary=summarize(rows),
            series=series,
            breakdown=breakdown,
            recent=recent,
            choices=choices,
            start=start,
            end=now,
            bucket_seconds=step,
            earliest=earliest,
            current_model=self.model,
            prices=self.settings(),
            error=self.error,
            retention_days=30,
            maximum_records=50000,
        )
