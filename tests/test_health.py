"""Health and support reports must remain useful without leaking world content."""

import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from roleweaver.diagnostics_log import DiagnosticsLog, FILE_COUNT
from roleweaver.health import bridge_health, PROTOCOLS, PLUGINS
from roleweaver.recovery_runtime import RecoveryRuntime


class LogTests(unittest.TestCase):
    def test_redaction_rotation_and_bounded_export(self):
        with tempfile.TemporaryDirectory() as folder:
            log = DiagnosticsLog(folder, max_bytes=1024)
            with patch(
                "roleweaver.diagnostics_log.time.monotonic",
                side_effect=range(0, 20000, 61),
            ):
                for _ in range(100):
                    log.record(
                        "provider_failed",
                        ValueError("sk-SECRET private dialogue"),
                        phase="private lore",
                        http_status=503,
                    )
            self.assertEqual(len(list(Path(folder).glob("*.jsonl"))), FILE_COUNT)
            self.assertTrue(
                all(p.stat().st_size <= 1024 for p in Path(folder).glob("*.jsonl"))
            )
            # Treat saved logs as untrusted, too: fields/values aren't copied raw.
            with log.path(0).open("a") as stream:
                stream.write(
                    json.dumps(
                        dict(
                            time=time.time(),
                            event="http_failed",
                            error="SECRET",
                            message="sk-SECRET",
                            phase="SECRET",
                            frames=[dict(file="../SECRET", line=1)],
                        )
                    )
                    + "\n"
                )
            report = json.dumps(log.export())
            self.assertNotIn("SECRET", report)
            self.assertNotIn("private", report)
            self.assertEqual(log.snapshot()["counts"]["provider_failed"], 100)

    def test_coalesces_concurrent_errors_and_recovers_after_disk_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            log = DiagnosticsLog(folder)
            threads = [
                threading.Thread(
                    target=lambda: [
                        log.record("bridge_failed", TimeoutError("SECRET"))
                        for _ in range(20)
                    ]
                )
                for _ in range(4)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(log.snapshot()["counts"]["bridge_failed"], 80)
            self.assertEqual(log.snapshot()["pending_repeats"], 79)
            self.assertEqual(len(log.export()), 1)
            with patch("pathlib.Path.open", side_effect=OSError("private path")):
                log.record("http_failed", OSError("SECRET"))
            self.assertTrue(log.write_failed)
            log.record("http_failed", OSError("SECRET"))
            self.assertFalse(log.write_failed)


class BridgeTests(unittest.TestCase):
    def hello(self):
        return dict(
            PROTOCOLS,
            seen=time.monotonic(),
            health_plugins={k: 1 for k in PLUGINS},
            translation_protocol=1,
        )

    def test_fresh_stale_old_and_incompatible_bridge(self):
        hello = self.hello()
        self.assertEqual(bridge_health(hello, True)["state"], "healthy")
        hello["actions_protocol"] = 99
        self.assertEqual(bridge_health(hello, True)["state"], "error")
        hello.pop("health_protocol")
        self.assertEqual(bridge_health(hello, True)["state"], "warning")
        hello["seen"] -= 30
        self.assertEqual(bridge_health(hello, True)["state"], "offline")

    def test_optional_translation_adapter_and_plugin_evidence(self):
        hello = self.hello()
        hello["health_plugins"]["RWTranslation"] = 0
        hello["translation_protocol"] = 0
        self.assertEqual(bridge_health(hello, False)["state"], "healthy")
        self.assertEqual(bridge_health(hello, True)["state"], "error")
        hello = self.hello()
        hello["health_plugins"]["Redis"] = "SECRET"
        hello["secret"] = "PRIVATE"
        health = bridge_health(hello, True)
        self.assertEqual(health["state"], "error")
        self.assertNotIn("SECRET", json.dumps(health))
        self.assertNotIn("PRIVATE", json.dumps(health))


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = RecoveryRuntime(
            self.root,
            dict(provider="offline", world_id="PRIVATEWORLD", api_key="sk-SECRET"),
            start_workers=False,
        )

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def collect(self, reachable=True):
        with (
            patch(
                "roleweaver.health.Redis.call",
                return_value="PONG" if reachable else "no",
            ),
            patch(
                "roleweaver.provider.open_url",
                side_effect=AssertionError("No LLM health probes"),
            ),
        ):
            self.runtime.monitor.collect()
        return self.runtime.monitor.snapshot()

    def test_health_and_report_are_allowlisted_and_no_llm_calls(self):
        app = self.runtime.app
        app.store.db.execute(
            "INSERT INTO messages(npc,player,text,created,speaker) VALUES ('PRIVATE_NPC','PRIVATE_PLAYER','SECRET_DIALOGUE',0,'player')"
        )
        app.store.db.commit()
        app.conversation_hello = dict(BridgeTests().hello(), name="PRIVATE_PLAYER")
        self.runtime.diagnostics.record(
            "bridge_failed", ValueError("sk-SECRET SECRET_DIALOGUE PRIVATE_PLAYER")
        )
        health = self.collect()
        self.assertEqual(health["components"]["redis"]["state"], "healthy")
        self.assertEqual(health["components"]["bridge"]["state"], "healthy")
        report = self.runtime.monitor.report()
        with zipfile.ZipFile(io.BytesIO(report)) as z:
            self.assertEqual(
                set(z.namelist()), {"health.json", "errors.jsonl", "README.txt"}
            )
            text = "".join(z.read(n).decode() for n in z.namelist())
        for secret in (
            "sk-SECRET",
            "SECRET_DIALOGUE",
            "PRIVATE_PLAYER",
            "PRIVATE_NPC",
            "PRIVATEWORLD",
            str(self.root),
        ):
            self.assertNotIn(secret, text)
        self.assertEqual(self.collect(False)["components"]["redis"]["state"], "error")

    def test_report_works_in_maintenance_and_recovery(self):
        self.runtime.maintenance = True
        self.assertEqual(self.collect()["components"]["companion"]["state"], "warning")
        self.runtime.maintenance = False
        self.runtime.app.close()
        self.runtime.app = None
        health = self.collect()
        self.assertEqual(health["components"]["companion"]["state"], "error")
        self.assertTrue(self.runtime.monitor.report().startswith(b"PK"))

    def test_provider_failures_include_fallback_attempts_not_content(self):
        app = self.runtime.app
        app.config["provider"] = "openai-compatible"
        app.config["llm_service"] = "gemini"
        event = dict(
            created=time.time(),
            model="PRIVATE_MODEL",
            duration_ms=200,
            request_bytes=50,
            request_chars=40,
            response_bytes=0,
            status="error",
            error="HTTPError",
            http_status=503,
            data={"private": "SECRET"},
        )
        app.usage.recorder("PRIVATE_NPC", "dialogue")(event)
        result = self.collect()["components"]["provider"]
        self.assertEqual(result["state"], "warning")
        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(result["failures_last_hour"], 1)
        self.assertEqual(
            self.runtime.diagnostics.snapshot()["recent"][-1]["http_status"], 503
        )
        event.update(status="success", error="", http_status=200)
        app.usage.recorder("PRIVATE_NPC", "dialogue")(event)
        result = self.collect()["components"]["provider"]
        self.assertEqual(result["attempts_last_hour"], 2)
        self.assertTrue(result["last_attempt_ok"])


if __name__ == "__main__":
    unittest.main()
