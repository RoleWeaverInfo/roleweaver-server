"""Overload must fail promptly, preserve credentials, and release busy state."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from roleweaver import provider
from roleweaver.resource_limits import BoundedExecutor, CapacityError, ProviderLimits
from roleweaver.llm_settings import ENDPOINTS
from tests import test_companions, test_companion_visits, test_checkins


class LimitTests(unittest.TestCase):
    def test_rate_window_failures_and_size(self):
        clock = [0]
        limits = ProviderLimits(dict(provider_attempts_per_minute=2), lambda: clock[0])
        for _ in range(2):
            with self.assertRaises(RuntimeError), limits.attempt(10):
                raise RuntimeError("failed HTTP call")
        self.assertEqual(limits.status()["active"], 0)
        with self.assertRaises(CapacityError), limits.attempt():
            self.fail("rate-limited request admitted")
        clock[0] = 60
        with limits.attempt():
            self.assertEqual(limits.status()["active"], 1)
        with self.assertRaises(CapacityError), limits.attempt(512 * 1024 + 1):
            self.fail("oversized request admitted")
        self.assertEqual(limits.status()["attempts_last_minute"], 1)

    def test_concurrent_admission_is_atomic(self):
        limits = ProviderLimits(dict(provider_max_concurrent=2))
        barrier = threading.Barrier(10)
        release = threading.Event()
        accepted = []

        def work():
            barrier.wait(timeout=5)
            try:
                with limits.attempt():
                    accepted.append(True)
                    release.wait(5)
                    return True
            except CapacityError:
                return False

        with ThreadPoolExecutor(max_workers=10) as pool:
            jobs = [pool.submit(work) for _ in range(10)]
            try:
                # All rejected jobs finish while the admitted jobs remain held.
                from concurrent.futures import wait, FIRST_COMPLETED

                wait(jobs, timeout=5, return_when=FIRST_COMPLETED)
                self.assertLessEqual(limits.status()["active"], 2)
                # Wait for eight refusals before allowing occupied slots to free.
                import time

                deadline = time.monotonic() + 5
                while sum(j.done() for j in jobs) < 8 and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(limits.status()["rejected_since_start"], 8)
            finally:
                release.set()
            self.assertEqual(sum(j.result() for j in jobs), 2)

    def test_executor_refuses_overflow_and_recovers_after_failure(self):
        release = threading.Event()
        pool = BoundedExecutor(max_workers=1, capacity=2)
        try:
            first = pool.submit(release.wait, 5)
            second = pool.submit(lambda: 42)
            with self.assertRaises(CapacityError):
                pool.submit(lambda: self.fail("overflow ran"))
            release.set()
            first.result(timeout=5)
            self.assertEqual(second.result(timeout=5), 42)

            def fail():
                raise RuntimeError("fixture")

            with self.assertRaises(RuntimeError):
                pool.submit(fail).result(timeout=5)
            self.assertEqual(
                pool.submit(lambda: "available").result(timeout=5), "available"
            )
        finally:
            release.set()
            pool.shutdown(wait=True)
        with self.assertRaises(RuntimeError):
            pool.submit(lambda: None)

    def test_fallback_attempts_share_budget_and_do_not_reset_preferred_on_overload(
        self,
    ):
        provider._gemini_preferred.clear()
        provider._gemini_cooldowns.clear()
        self.addCleanup(provider._gemini_preferred.clear)
        self.addCleanup(provider._gemini_cooldowns.clear)
        limits = ProviderLimits(dict(provider_attempts_per_minute=1))
        model = "gemini-3.7-flash"
        config = dict(
            _provider_limits=limits, llm_service="gemini", gemini_fallback_on_busy=True
        )
        headers = {"Authorization": "Bearer fixture-private"}
        key = (model, hashlib.sha256(headers["Authorization"].encode()).digest())
        provider._gemini_preferred[key] = "gemini-3.6-flash"
        with limits.attempt():
            pass
        with patch("roleweaver.provider.open_url") as request:
            with self.assertRaises(CapacityError):
                provider.complete(
                    ENDPOINTS["gemini"] + "/chat/completions",
                    json.dumps(dict(model=model, messages=[])).encode(),
                    headers,
                    30,
                    1000,
                    lambda x: x,
                    config,
                )
            request.assert_not_called()
        self.assertEqual(provider._gemini_preferred[key], "gemini-3.6-flash")
        limits = ProviderLimits(dict(provider_attempts_per_minute=1))
        config["_provider_limits"] = limits
        with patch(
            "roleweaver.provider.open_url",
            side_effect=HTTPError(
                "https://fixture.invalid", 503, "busy", {}, io.BytesIO()
            ),
        ) as request:
            with self.assertRaises(CapacityError):
                provider.complete(
                    ENDPOINTS["gemini"] + "/chat/completions",
                    json.dumps(dict(model=model, messages=[])).encode(),
                    headers,
                    30,
                    1000,
                    lambda x: x,
                    config,
                )
            self.assertEqual(request.call_count, 1)


class CompanionOverloadTests(unittest.TestCase):
    setUp = test_companions.CompanionTests.setUp
    tearDown = test_companions.CompanionTests.tearDown
    event = test_companions.CompanionTests.event

    def test_overflow_does_not_leave_companion_busy(self):
        self.app.config["companions_enabled"] = True
        with patch.object(self.app.pool, "submit", side_effect=CapacityError("busy")):
            self.app.event(self.event())
        self.assertFalse(self.app.companion_work)
        self.assertFalse(self.app.companion_pending)
        self.assertFalse(self.app.redis.commands)
        self.assertEqual(self.app.guard_counts["rate_limited"], 1)

    def test_saved_provider_switch_and_probe_retain_shared_limiter(self):
        limiter = self.app.provider_limits
        body = dict(service="offline", revision=self.app.llm_status()["revision"])
        self.app.save_llm(body)
        self.assertIs(self.app.config["_provider_limits"], limiter)
        with patch(
            "roleweaver.llm_settings.open_url", return_value=io.BytesIO(b'{"data":[]}')
        ) as call:
            result = self.app.probe_llm(
                dict(service="lmstudio", model="", base_url="http://127.0.0.1:1234/v1"),
                models=True,
            )
        self.assertEqual(result, dict(models=[]))
        self.assertEqual(call.call_count, 1)
        self.assertEqual(limiter.status()["attempts_last_minute"], 1)
        self.assertNotIn("_provider_limits", self.app.llm.path.read_text())
        with (
            patch.object(
                limiter, "attempt", side_effect=CapacityError("Shared limit reached")
            ),
            patch("roleweaver.llm_settings.open_url") as call,
            self.assertRaisesRegex(CapacityError, "Shared limit reached"),
        ):
            self.app.probe_llm(
                dict(service="lmstudio", model="", base_url="http://127.0.0.1:1234/v1"),
                models=True,
            )
        call.assert_not_called()


class VisitOverloadTests(unittest.TestCase):
    setUp = test_companion_visits.VisitServiceTests.setUp
    tearDown = test_companion_visits.VisitServiceTests.tearDown
    event = test_companion_visits.VisitServiceTests.event
    run_chat = test_companion_visits.VisitServiceTests.run_chat
    start = test_companion_visits.VisitServiceTests.start
    visit_event = test_companion_visits.VisitServiceTests.visit_event
    push_state = test_companion_visits.VisitServiceTests.push_state

    def test_visit_returns_without_inventing_reply_when_queue_full(self):
        self.start()
        with patch.object(self.app.pool, "submit", side_effect=CapacityError("busy")):
            self.push_state("ask", 1)
        self.assertFalse(self.app.companion_work)
        self.assertFalse(self.item["working"])
        self.assertEqual(self.app.redis.last()["action"], "return")
        self.assertEqual(self.item["heard"], [])


class CheckinOverloadTests(unittest.TestCase):
    setUp = test_checkins.CheckinTests.setUp
    tearDown = test_checkins.CheckinTests.tearDown
    ready = test_checkins.CheckinTests.ready

    def test_refused_checkin_releases_scene(self):
        item = self.ready()
        self.app.checkin_working = 1
        with patch.object(self.app.pool, "submit", side_effect=CapacityError("busy")):
            self.app.queue_checkin(item)
        self.assertEqual(self.app.checkin_working, 0)
        self.assertIsNone(self.app.checkin)
