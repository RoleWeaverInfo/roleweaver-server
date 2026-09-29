"""Owner-facing translation diagnostics without reading or exporting cached text.

These checks observe existing work only. They never queue jobs, retry failures,
call a provider or inspect player identities. In-game exclusions and unreached
dialogue nodes cannot be counted here because they never reach the addon.
"""

from contextlib import closing
import math
import sqlite3
import time

from .diagnostics_log import ERRORS, number
from .health import bridge_health
from .translation import KINDS, LANGUAGES


def advice(error, code=None):
    if code in (401, 403):
        return "Check the API key and model access in LLM Settings."
    if code == 429:
        return "Provider quota or rate limit reached. Check quota and lower the job limit if needed."
    if type(code) is int and code >= 500:
        return "The provider is unavailable or busy. Reopen the text later; check configured model fallbacks."
    if error in ("TimeoutError", "URLError", "ConnectionError"):
        return "The provider did not respond in time or could not be reached. Check its connection and model availability."
    if error in ("ValueError", "JSONDecodeError"):
        return "The response was unusable or failed translation validation. Try another model if this repeats."
    return "Check Health & Support and download a report if this repeats."


def snapshot(app):
    with app.lock:
        cache = app.translations
        config = dict(app.config)
        hello = dict(app.conversation_hello)
        worker = getattr(app, "translation_thread", None)
    now = time.monotonic()
    with cache.lock:
        settings = cache.config()
        counts = {s: 0 for s in ("ready", "pending", "failed", "missing", "obsolete")}
        languages, kinds = {}, {}
        for target, kind, state, count in cache.db.execute(
            "SELECT target,kind,status,COUNT(*) FROM entries GROUP BY target,kind,status"
        ):
            if target not in LANGUAGES or kind not in KINDS or state not in counts:
                continue
            counts[state] += count
            for group, key in ((languages, target), (kinds, kind)):
                group.setdefault(key, {s: 0 for s in counts})[state] += count
        window = [stamp for stamp in cache.window if stamp >= now - 60]
        wait = (
            max(0, math.ceil(window[0] + 60 - now))
            if len(window) >= settings["per_minute"]
            else 0
        )
        active = cache.active_job
        active_seconds = round(now - active, 1) if active is not None else None
        last = dict(cache.last_job) if cache.last_job else None
        if last and last["error"]:
            last["advice"] = advice(last["error"])
        queued, hits, full = len(cache.jobs), cache.hits, cache.queue_full
        worker_error = (
            cache.worker_error
            if cache.worker_error in ERRORS
            else "Error" if cache.worker_error else ""
        )
    provider = config.get("llm_service", config.get("provider", "offline"))
    provider = (
        provider if provider in ("offline", "openai", "gemini", "lmstudio") else "other"
    )
    bridge = bridge_health(hello, settings["enabled"])
    requests, failures = {}, []
    with app.usage.lock, closing(sqlite3.connect(app.usage.path, timeout=1)) as db:
        row = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(status='error'),0),AVG(duration_ms),SUM(input_tokens),SUM(output_tokens),SUM(cost_usd),COUNT(cost_usd) "
            "FROM requests WHERE phase='translation' AND created>=?",
            (time.time() - 3600,),
        ).fetchone()
        requests = dict(
            attempts=row[0],
            failed=row[1],
            mean_ms=round(row[2], 1) if number(row[2]) is not None else None,
            input_tokens=number(row[3]),
            output_tokens=number(row[4]),
            estimated_cost_usd=number(row[5]),
            priced_attempts=row[6],
        )
        for stamp, error, code in db.execute(
            "SELECT created,error,http_status FROM requests WHERE phase='translation' AND status='error' ORDER BY id DESC LIMIT 10"
        ):
            error = error if error in ERRORS else "Error"
            code = code if type(code) is int and 100 <= code <= 599 else None
            failures.append(
                dict(
                    time=number(stamp),
                    error=error,
                    http_status=code,
                    advice=advice(error, code),
                )
            )
    running = bool(worker and worker.is_alive())
    if not settings["enabled"]:
        state, message = (
            "disabled",
            "Translation is turned off. Enable it below when ready.",
        )
    elif provider == "offline":
        state, message = (
            "warning",
            "Choose an online provider or LM Studio in LLM Settings before translating.",
        )
    elif not running or worker_error:
        state, message = (
            "error",
            "The translation worker is stopped or has reported an error. Open Health & Support.",
        )
    elif bridge["state"] != "healthy":
        state, message = "warning", bridge["detail"]
    elif active is not None:
        state, message = (
            "working",
            "A translation request is in progress. Players can continue using original text.",
        )
    elif queued and wait:
        state, message = (
            "waiting",
            "Jobs are waiting for the configured per-minute limit. No action is needed.",
        )
    elif queued:
        state, message = "working", "Translation jobs are queued."
    else:
        state, message = (
            "ready",
            "Waiting for players to view supported text. Nothing is translated ahead of demand.",
        )
    return dict(
        schema=1,
        sampled_at=time.time(),
        state=state,
        message=message,
        enabled=settings["enabled"],
        source=settings["source"],
        languages=settings["languages"],
        per_minute=settings["per_minute"],
        provider=provider,
        worker_running=running,
        worker_error=worker_error,
        pending=queued,
        active_seconds=active_seconds,
        rate_wait_seconds=wait,
        cache_hits=hits,
        queue_full_since_start=full,
        counts=counts,
        by_language=languages,
        by_kind=kinds,
        last_job=last,
        recent_failures=failures,
        requests_last_hour=requests,
        native_adapter=bridge,
    )
