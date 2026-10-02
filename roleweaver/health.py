"""Read-only health sampling and allowlisted, content-free support archives.

The monitor belongs to RecoveryRuntime, not Service, so it survives a corrupt
database or restore. A lease protects every application read from database swaps.
Redis PING runs outside that lease; no probe sends a request to an LLM.
"""

from contextlib import closing
import copy
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import threading
import time
import zipfile

from . import __version__
from .diagnostics_log import number
from .redis_wire import Redis

PROTOCOLS = {
    "health_protocol": 1,
    "conversation_protocol": 2,
    "actions_protocol": 6,
    "live_protocol": 1,
    "inventory_protocol": 1,
}
PLUGINS = (
    "Core",
    "Chat",
    "Events",
    "Redis",
    "Creature",
    "Player",
    "Item",
    "Dialog",
    "Util",
    "RWTranslation",
)


def component(state, detail, **metrics):
    return dict(state=state, detail=detail, **metrics)


def bridge_health(hello, translations_enabled):
    age = (
        max(0, time.monotonic() - hello["seen"])
        if number(hello.get("seen")) is not None
        else None
    )
    fresh = age is not None and age < 5
    observed = {
        key: (
            value
            if type(value := hello.get(key)) is int and 0 <= value <= 1000
            else None
        )
        for key in PROTOCOLS
    }
    raw = hello.get("health_plugins", {})
    raw = raw if isinstance(raw, dict) else {}
    plugins = {
        name: (
            raw.get(name) == 1
            if type(raw.get(name)) is int and raw.get(name) in (0, 1)
            else None
        )
        for name in PLUGINS
    }
    adapter = hello.get("translation_protocol")
    adapter = adapter if type(adapter) is int and 0 <= adapter <= 1000 else None
    data = dict(
        heartbeat_age_seconds=round(age, 1) if age is not None else None,
        expected_protocols=PROTOCOLS,
        observed_protocols=observed,
        plugins=plugins,
        translation_protocol=adapter,
    )
    if not fresh:
        return component(
            "offline",
            "No recent game heartbeat. If NWN is meant to be running, check its launcher, module hooks and Redis world/prefix settings. Plugin observations below may be stale.",
            **data,
        )
    if observed["health_protocol"] is None:
        return component(
            "warning",
            "Game connected, but its bridge predates health reporting. Install the updated bridge scripts and restart NWN when convenient.",
            **data,
        )
    if any(observed[k] != v for k, v in PROTOCOLS.items()):
        return component(
            "error",
            "Bridge protocol mismatch. Install bridge scripts from the same package as this Role Weaver Addon.",
            **data,
        )
    needed = PLUGINS[:7] + (
        ("Dialog", "Util", "RWTranslation") if translations_enabled else ()
    )
    if any(plugins[p] is not True for p in needed):
        return component(
            "error",
            "A required plugin is missing or unreported. Check the plugin rows and NWNX startup settings.",
            **data,
        )
    if translations_enabled and adapter != 1:
        return component(
            "error",
            "The per-player dialogue translation adapter has an incompatible protocol. Install the matching NWNX_RWTranslation build.",
            **data,
        )
    return component(
        "healthy",
        "Game heartbeat and required plugin/protocol checks passed. This does not validate every module event hook or gameplay action.",
        **data,
    )


class HealthMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.sampled = 0
        self.data = dict(
            components={
                "monitor": component("unknown", "Waiting for the first health sample.")
            }
        )
        root = Path(__file__).parent
        digest = hashlib.sha256()
        for path in sorted(
            [
                *root.rglob("*.py"),
                *root.glob("static/*.js"),
                *root.glob("static/*.html"),
            ]
        ):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
        self.build = dict(
            application=__version__,
            source_sha256=digest.hexdigest(),
            python=platform.python_version(),
            sqlite=sqlite3.sqlite_version,
            platform=(
                "Windows"
                if platform.system() == "Windows"
                else "Linux" if platform.system() == "Linux" else "Other"
            ),
            architecture=(
                "64-bit" if platform.architecture()[0] == "64bit" else "32-bit"
            ),
        )

    def start(self):
        if self.thread:
            return

        def run():
            while not self.stop.is_set():
                self.collect()
                self.stop.wait(5)

        self.thread = threading.Thread(target=run, name="health-monitor", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join()

    def application(self, app):
        with app.lock:
            hello = copy.deepcopy(app.conversation_hello)
            busy, pending = len(app.busy), len(app.pending)
            provider = app.config.get(
                "llm_service", app.config.get("provider", "offline")
            )
            provider = (
                provider
                if provider in ("offline", "openai", "gemini", "lmstudio")
                else "other"
            )
        cache = app.translations
        with cache.lock:
            enabled = cache.config()["enabled"]
            cache_counts = {s: 0 for s in ("ready", "pending", "failed")}
            for status, count in cache.db.execute(
                "SELECT status, COUNT(*) FROM entries GROUP BY status"
            ):
                if status in cache_counts:
                    cache_counts[status] = count
            queue, hits, failed = len(cache.jobs), cache.hits, bool(cache.worker_error)
        alive = {
            key: bool(getattr(app, name, None) and getattr(app, name).is_alive())
            for key, name in (
                ("bridge", "bridge_thread"),
                ("translation", "translation_thread"),
            )
        }
        workers_expected = self.runtime.workers
        workers_ok = all(alive.values()) or not workers_expected
        with app.usage.lock, closing(sqlite3.connect(app.usage.path, timeout=1)) as db:
            total, errors, duration = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(status!='success'),0), AVG(duration_ms) FROM requests WHERE created>=?",
                (time.time() - 3600,),
            ).fetchone()
            last = db.execute(
                "SELECT created,status FROM requests ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            "bridge": bridge_health(hello, enabled),
            "workers": component(
                "healthy" if workers_ok else "error",
                (
                    "Background worker threads are running."
                    if workers_expected and workers_ok
                    else "Worker threads are stopped or not started."
                ),
                **alive,
                active_replies=busy,
                pending_commands=pending,
                ai_work_capacity=app.pool.capacity,
            ),
            "translations": component(
                (
                    "disabled"
                    if not enabled
                    else (
                        "error"
                        if failed
                        else "warning" if cache_counts["failed"] else "healthy"
                    )
                ),
                (
                    "Translation is disabled."
                    if not enabled
                    else (
                        "Some translations failed; inspect recent errors and provider health. Original text remains available."
                        if failed or cache_counts["failed"]
                        else "Translation cache is available."
                    )
                ),
                entries=cache_counts,
                queued=queue,
                cache_hits_since_start=hits,
            ),
            "provider": component(
                (
                    "disabled"
                    if provider == "offline"
                    else (
                        "warning"
                        if errors or app.usage.error
                        else "unknown" if not total else "healthy"
                    )
                ),
                "Observed request history only; health checks make no LLM calls. Failures may include attempts that succeeded through a fallback model.",
                provider=provider,
                request_limits=app.provider_limits.status(),
                attempts_last_hour=total,
                failures_last_hour=errors,
                mean_duration_ms=(
                    round(duration, 1) if number(duration) is not None else None
                ),
                last_attempt_age_seconds=(
                    max(0, round(time.time() - last[0]))
                    if last and number(last[0]) is not None
                    else None
                ),
                last_attempt_ok=last[1] == "success" if last else None,
                usage_write_failed=bool(app.usage.error),
            ),
        }

    def collect(self):
        runtime = self.runtime
        parts = {}
        try:
            # Cached database checks run on the recovery schedule, not every
            # five seconds. Never execute an integrity scan in an HTTP request.
            with runtime.condition:
                health = copy.deepcopy(runtime.health)
                files = copy.deepcopy(runtime.files)
                available, maintenance = runtime.app is not None, runtime.maintenance
                config = dict(runtime.manager.config)
                warning = bool(runtime.manager.last_error)
                checked = runtime.health_checked
            parts["companion"] = component(
                "warning" if maintenance else "healthy" if available else "error",
                (
                    "Maintenance is in progress."
                    if maintenance
                    else (
                        "Role Weaver Addon is available."
                        if available
                        else "Role Weaver Addon startup failed. Open Database & Recovery to inspect and restore data."
                    )
                ),
            )
            database_ok = bool(health) and all(
                v.get("ok") is True for v in health.values()
            )
            parts["databases"] = component(
                "healthy" if database_ok else "error",
                (
                    "Last scheduled/startup integrity checks passed."
                    if database_ok
                    else "Database checks found a problem. Open Database & Recovery."
                ),
                checked_at=checked,
                databases={
                    kind: dict(
                        ok=value.get("ok") is True,
                        missing=value.get("missing") is True,
                        bytes=number(value.get("bytes")) or 0,
                        wal_bytes=number(value.get("wal_bytes")) or 0,
                    )
                    for kind, value in health.items()
                    if kind in ("world", "translations", "usage")
                },
            )
            verified = [
                p
                for p in files
                if p.get("verified") is True and number(p.get("created")) is not None
            ]
            age = (
                max(0, time.time() - max(p["created"] for p in verified))
                if verified
                else None
            )
            stale = config["enabled"] and (
                age is None or age > config["interval_minutes"] * 120 + 60
            )
            parts["backups"] = component(
                (
                    "error"
                    if warning
                    else (
                        "warning"
                        if stale
                        else "healthy" if config["enabled"] else "disabled"
                    )
                ),
                (
                    "A backup operation reported a problem. Open Database & Recovery."
                    if warning
                    else (
                        "No recent verified recovery point; check the backup schedule."
                        if stale
                        else (
                            "Recovery points are available."
                            if verified
                            else "Automatic backups are disabled and no verified recovery points exist."
                        )
                    )
                ),
                automatic=config["enabled"],
                verified_points=len(verified),
                latest_age_seconds=round(age) if age is not None else None,
            )
            free = shutil.disk_usage(runtime.directory).free
            parts["disk"] = component(
                "healthy" if free >= config["min_free_mb"] * 1048576 else "warning",
                "Free disk space compared with the configured backup reserve.",
                free_bytes=free,
                reserve_bytes=config["min_free_mb"] * 1048576,
            )
            if available and not maintenance:
                try:
                    with runtime.lease() as app:
                        parts.update(self.application(app))
                except ValueError:
                    if not runtime.maintenance and runtime.app is not None:
                        raise
            if "bridge" not in parts:
                parts["bridge"] = component(
                    "unknown",
                    "Application checks are unavailable during recovery or maintenance.",
                )
        except Exception as exc:
            runtime.diagnostics.record("health_probe_failed", exc)
            parts["application_probe"] = component(
                "error",
                "An application health check failed. Download a support report; other checks remain available.",
            )
        before = time.monotonic()
        try:
            ok = (
                Redis(port=runtime.config.get("redis_port", 6379)).call("PING")
                == "PONG"
            )
            parts["redis"] = component(
                "healthy" if ok else "error",
                (
                    "Redis responded to PING."
                    if ok
                    else "Redis returned an unexpected PING response."
                ),
                latency_ms=round((time.monotonic() - before) * 1000, 1),
            )
        except Exception:
            parts["redis"] = component(
                "error",
                "Cannot reach Redis. Check the Redis service and Role Weaver Addon redis_port setting.",
            )
        with self.lock:
            self.data = dict(sampled_at=time.time(), build=self.build, components=parts)
            self.sampled = time.monotonic()

    def snapshot(self):
        with self.lock:
            data = copy.deepcopy(self.data)
            data["sample_age_seconds"] = (
                round(max(0, time.monotonic() - self.sampled), 1)
                if self.sampled
                else None
            )
        logs = self.runtime.diagnostics.snapshot()
        data["uptime_seconds"] = round(time.monotonic() - self.started)
        data["diagnostics"] = logs
        if logs["write_failed"]:
            data["components"]["error_log"] = component(
                "error",
                "Cannot write the diagnostic log. Check disk space and data/logs permissions. Recent in-memory errors are still included.",
            )
        if data["sample_age_seconds"] is not None and data["sample_age_seconds"] > 15:
            data["components"]["monitor"] = component(
                "warning", "Health information is stale; a probe may be blocked."
            )
        return data

    def report(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("health.json", json.dumps(self.snapshot(), indent=2))
            archive.writestr(
                "errors.jsonl",
                "".join(
                    json.dumps(row) + "\n" for row in self.runtime.diagnostics.export()
                ),
            )
            archive.writestr(
                "README.txt",
                "Role Weaver support report (schema 1)\n\nContains sampled component health, source fingerprint, counts and filtered technical errors.\nNo configurations, credentials, addresses, world/player/NPC identifiers, conversations, lore, prompts, translations, database contents or raw engine logs are exported.\nException messages and local variables are omitted. Source frames show project-relative Python file and line only.\nLogs rotate at 1 MiB each (four files). Export keeps at most 1,000 records. Repeated errors are coalesced for 60 seconds; health.json includes in-memory counts since startup and recent errors.\nProvider history records attempts, including failed fallback attempts. No paid provider check is performed. A fresh heartbeat confirms loaded plugins/protocols, not full gameplay correctness or engine ABI compatibility.\nReview these files before sharing and add your reproduction steps and NWN/NWNX build versions separately.\n",
            )
        return output.getvalue()
