"""Shared, non-waiting admission limits; never hold a game lock for network IO."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import threading
import time


class CapacityError(ValueError):
    """Work was refused before contacting a provider or entering a worker queue."""


class BoundedExecutor(ThreadPoolExecutor):
    """Bound unfinished jobs; release capacity on completion or shutdown cancellation."""

    def __init__(self, max_workers=4, capacity=8):
        super().__init__(max_workers=max_workers, thread_name_prefix="roleweaver")
        self.slots = threading.BoundedSemaphore(capacity)
        self.capacity = capacity

    def submit(self, fn, /, *args, **kwargs):
        if not self.slots.acquire(blocking=False):
            raise CapacityError("AI workers are busy; try again shortly")
        try:
            future = super().submit(fn, *args, **kwargs)
        except BaseException:
            self.slots.release()
            raise
        future.add_done_callback(lambda _: self.slots.release())
        return future


class ProviderLimits:
    """Count actual outbound attempts, including reviews, retries and probes.

    One instance belongs to one running Role Weaver service. Copied provider
    settings retain the same limiter, and changing models does not reset it.
    It stores only counters/timestamps, never text, identities or credentials.
    """

    MAX_REQUEST_BYTES = 512 * 1024

    def __init__(self, config, clock=time.monotonic):
        self.concurrent = self._setting(config, "provider_max_concurrent", 4, 8)
        self.per_minute = self._setting(
            config, "provider_attempts_per_minute", 180, 600
        )
        self.clock = clock
        self.lock = threading.Lock()
        self.recent = deque()
        self.active = self.rejected = 0

    @staticmethod
    def _setting(config, name, default, maximum):
        value = config.get(name, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be an integer between 1 and {maximum}")
        return value

    def _expire(self):
        cutoff = self.clock() - 60
        while self.recent and self.recent[0] <= cutoff:
            self.recent.popleft()

    @contextmanager
    def attempt(self, request_bytes=0):
        with self.lock:
            self._expire()
            if request_bytes > self.MAX_REQUEST_BYTES:
                self.rejected += 1
                raise CapacityError("LLM request exceeds the 512 KiB size limit")
            if self.active >= self.concurrent or len(self.recent) >= self.per_minute:
                self.rejected += 1
                raise CapacityError(
                    "Shared LLM request limit reached; try again shortly"
                )
            self.active += 1
            self.recent.append(self.clock())
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1

    def status(self):
        with self.lock:
            self._expire()
            return dict(
                active=self.active,
                max_concurrent=self.concurrent,
                attempts_last_minute=len(self.recent),
                attempts_per_minute=self.per_minute,
                rejected_since_start=self.rejected,
                max_request_bytes=self.MAX_REQUEST_BYTES,
            )
