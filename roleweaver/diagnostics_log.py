"""Bounded support logs containing codes and source locations, never game text.

This is deliberately not a general-purpose logging sink. Exception messages,
locals, request bodies, model output and arbitrary metadata never enter it.
The same allowlist is applied again when existing files are read for export.
"""

from collections import Counter, deque
import json
import math
import os
from pathlib import Path
import threading
import time

EVENTS = {
    "companion_start_failed",
    "recovery_failed",
    "bridge_failed",
    "game_confirmation_timeout",
    "translation_worker_failed",
    "translation_job_failed",
    "provider_failed",
    "usage_write_failed",
    "http_failed",
    "health_probe_failed",
}
ERRORS = {
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "OSError",
    "PermissionError",
    "FileNotFoundError",
    "ConnectionError",
    "ConnectionRefusedError",
    "ConnectionResetError",
    "TimeoutError",
    "HTTPError",
    "URLError",
    "JSONDecodeError",
    "UnicodeDecodeError",
    "DatabaseError",
    "OperationalError",
    "IntegrityError",
    "RuntimeError",
}
PHASES = {
    "dialogue",
    "input_review",
    "output_review",
    "connection_test",
    "translation",
    "director",
    "proposal",
    "social",
    "unknown",
}
MAX_BYTES = 1024 * 1024
FILE_COUNT = 4  # Active file plus three older files: at most 4 MiB.


def number(value, maximum=10**15):
    return (
        value
        if type(value) in (int, float)
        and math.isfinite(value)
        and 0 <= value <= maximum
        else None
    )


class DiagnosticsLog:
    def __init__(self, directory, max_bytes=MAX_BYTES):
        self.directory = Path(directory)
        self.max_bytes = max_bytes
        self.lock = threading.RLock()
        self.counts = Counter()
        self.last_written = {}
        self.recent = deque(maxlen=100)
        self.write_failed = False
        self.root = Path(__file__).parent
        self.sources = {
            p.relative_to(self.root).as_posix() for p in self.root.rglob("*.py")
        }

    def path(self, index):
        return self.directory / (
            "errors.jsonl" if index == 0 else f"errors.{index}.jsonl"
        )

    def clean(self, row):
        if not isinstance(row, dict) or row.get("event") not in EVENTS:
            return None
        stamp = number(row.get("time"))
        if stamp is None:
            return None
        result = dict(
            time=stamp,
            event=row["event"],
            error=row.get("error") if row.get("error") in ERRORS else "Error",
        )
        result["count"] = number(row.get("count"), 10**12) or 1
        result["phase"] = row.get("phase") if row.get("phase") in PHASES else "unknown"
        code = row.get("http_status")
        if type(code) is int and 100 <= code <= 599:
            result["http_status"] = code
        result["frames"] = []
        frames = row.get("frames", [])
        for frame in frames[-6:] if isinstance(frames, list) else []:
            if isinstance(frame, dict) and frame.get("file") in self.sources:
                line = frame.get("line")
                if type(line) is int and 1 <= line <= 100000:
                    result["frames"].append(dict(file=frame["file"], line=line))
        return result

    def record(self, event, exc=None, *, error=None, phase=None, http_status=None):
        """Never raise into application work, even when the log disk is full."""
        try:
            frames = []
            tb = exc.__traceback__ if exc is not None else None
            while tb:
                try:
                    name = (
                        Path(tb.tb_frame.f_code.co_filename)
                        .resolve()
                        .relative_to(self.root.resolve())
                        .as_posix()
                    )
                    frames.append(dict(file=name, line=tb.tb_lineno))
                except ValueError:
                    pass
                tb = tb.tb_next
            row = self.clean(
                dict(
                    time=time.time(),
                    event=event,
                    error=type(exc).__name__ if exc is not None else error,
                    phase=phase,
                    http_status=http_status,
                    frames=frames,
                )
            )
            if row is None:
                return
            with self.lock:
                self.counts[event] += 1
                self.recent.append(row)
                signature = (event, row["error"], row["phase"], row.get("http_status"))
                previous, suppressed = self.last_written.get(signature, (-1e9, 0))
                now = time.monotonic()
                if now - previous < 60:
                    self.last_written[signature] = (previous, suppressed + 1)
                    return
                row["count"] = suppressed + 1
                self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                packet = (json.dumps(row, separators=(",", ":")) + "\n").encode()
                path = self.path(0)
                if path.exists() and path.stat().st_size + len(packet) > self.max_bytes:
                    self.path(FILE_COUNT - 1).unlink(missing_ok=True)
                    for i in range(FILE_COUNT - 2, -1, -1):
                        if self.path(i).exists():
                            os.replace(self.path(i), self.path(i + 1))
                with path.open("ab") as stream:
                    os.chmod(path, 0o600)
                    stream.write(packet)
                self.last_written[signature] = (now, 0)
                self.write_failed = False
        except Exception:
            self.write_failed = True

    def snapshot(self):
        with self.lock:
            return dict(
                write_failed=self.write_failed,
                counts=dict(self.counts),
                pending_repeats=sum(v[1] for v in self.last_written.values()),
                recent=list(self.recent)[-20:],
            )

    def export(self):
        """Read only our four bounded files, rejecting malformed or extra data."""
        rows = deque(maxlen=1000)
        with self.lock:
            for index in reversed(range(FILE_COUNT)):
                try:
                    with self.path(index).open("rb") as stream:
                        # A tampered oversized file cannot turn a report into an
                        # unbounded allocation. Partial final lines are ignored.
                        data = stream.read(self.max_bytes)
                    for line in data.splitlines():
                        if len(line) > 4096:
                            continue
                        try:
                            clean = self.clean(json.loads(line))
                            if clean:
                                rows.append(clean)
                        except (ValueError, TypeError):
                            pass
                except OSError:
                    pass
        return list(rows)


def record(owner, event, exc=None, **details):
    """Optional hook keeps Service, Usage and TranslationCache usable on their own."""
    log = getattr(owner, "support_log", None)
    if log is not None:
        log.record(event, exc, **details)
