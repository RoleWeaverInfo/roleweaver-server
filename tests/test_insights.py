from contextlib import closing
import concurrent.futures
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from roleweaver import provider, safeguards
from roleweaver.store import Store, DEFAULT_NPC
from roleweaver.service import Service
from roleweaver.knowledge import inspect_knowledge
from roleweaver.usage import Usage, counts, estimate, price

CONFIG = dict(
    provider="openai-compatible",
    base_url="https://provider.invalid/v1",
    model="test-model",
)


def event(usage=None, **overrides):
    return dict(
        created=time.time(),
        duration_ms=100,
        request_bytes=1024,
        request_chars=100,
        response_bytes=200,
        status="success",
        error="",
        http_status=200,
        data={"usage": usage or {}},
        **overrides,
    )


class Response(io.BytesIO):
    status = 200


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "usage.sqlite3"
        self.usage = Usage(self.path, CONFIG)

    def tearDown(self):
        self.temp.cleanup()

    def test_known_cached_reasoning_and_unknown_counts(self):
        c = counts(
            {
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 200,
                    "prompt_tokens_details": {"cached_tokens": 400},
                    "completion_tokens_details": {"reasoning_tokens": 50},
                }
            }
        )
        self.assertAlmostEqual(estimate(c, dict(input=2, output=8, cached=0.5)), 0.003)
        self.assertIsNone(estimate(counts({}), dict(input=2, output=8, cached=0.5)))
        self.assertIsNone(estimate(c, None))
        self.assertEqual(
            counts({"usage": {"prompt_tokens": True, "completion_tokens": -2}})[
                "input_tokens"
            ],
            None,
        )
        self.assertIsNone(
            counts(
                {
                    "usage": {
                        "prompt_tokens": 2,
                        "prompt_tokens_details": {"cached_tokens": 3},
                    }
                }
            )["cached_tokens"]
        )
        self.assertEqual(
            counts({"usage": {"input_tokens": 10, "output_tokens": 4}})["input_tokens"],
            10,
        )
        self.assertIsNone(
            estimate(c, dict(input=2, output=8, cached=0.5, max_input_tokens=999))
        )

    def test_rates_validate_and_snapshot_without_retroactive_repricing(self):
        for bad in (float("nan"), float("inf"), -1, True, "2"):
            with self.assertRaises(ValueError):
                price(dict(input=bad, output=2, cached=None))
        self.usage.save_price("test-model", dict(input=2, output=8, cached=None))
        record = self.usage.recorder("mira", "dialogue")
        self.usage.save_price("test-model", dict(input=20, output=80, cached=None))
        record(event({"prompt_tokens": 1000, "completion_tokens": 200}))
        self.assertAlmostEqual(self.usage.report()["summary"]["cost_usd"], 0.0036)
        reopened = Usage(self.path, CONFIG)
        self.assertEqual(reopened.settings()["test-model"]["input"], 20)
        self.assertAlmostEqual(reopened.report()["summary"]["cost_usd"], 0.0036)
        other = Usage(self.path, dict(CONFIG, base_url="https://different.invalid/v1"))
        self.assertEqual(other.settings(), {})

    def test_filters_partial_coverage_errors_and_retention(self):
        self.usage.save_price("test-model", dict(input=2, output=8, cached=None))
        self.usage.recorder("mira", "dialogue")(
            event({"prompt_tokens": 1000, "completion_tokens": 200})
        )
        e = event()
        e.update(
            status="error", error="TimeoutError", http_status=None, duration_ms=900
        )
        self.usage.recorder("orren", "input_review")(e)
        report = self.usage.report()
        s = report["summary"]
        self.assertEqual(
            (s["requests"], s["errors"], s["token_requests"], s["priced_requests"]),
            (2, 1, 1, 1),
        )
        self.assertEqual(s["p95_ms"], 900)
        self.assertEqual(sum(b["requests"] for b in report["series"]), 2)
        self.assertEqual(
            self.usage.report(npc="mira", phase="dialogue")["summary"]["requests"], 1
        )
        self.assertEqual(self.usage.report(npc="missing")["summary"]["cost_usd"], None)
        old = event()
        old["created"] = time.time() - 31 * 86400
        self.usage.recorder("mira", "dialogue")(old)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 2
            )
        with self.assertRaises(ValueError):
            self.usage.report(window="unbounded")

    def test_concurrent_recorders_preserve_records(self):
        def work(i):
            self.usage.recorder("npc" + str(i % 4), "dialogue")(
                event({"prompt_tokens": 10, "completion_tokens": 2})
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(work, range(40)))
        self.assertEqual(self.usage.report()["summary"]["requests"], 40)
        self.assertEqual(self.usage.report()["summary"]["input_tokens"], 400)

    def test_actual_http_size_usage_success_failure_no_text_stored(self):
        payload = {
            "choices": [{"message": {"content": "PRIVATE_REPLY"}}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 4},
        }
        captured = []

        def urlopen(request, **kw):
            captured.append(request)
            return Response(json.dumps(payload).encode())

        profile = dict(DEFAULT_NPC, lore="PRIVATE_LORE")
        with (
            provider.observe_requests(self.usage.recorder("mira", "dialogue")),
            patch("roleweaver.provider.open_url", side_effect=urlopen),
        ):
            self.assertEqual(
                provider.reply(
                    CONFIG,
                    profile,
                    [],
                    [dict(speaker="player", text="PRIVATE_PLAYER_TEXT")],
                ),
                "PRIVATE_REPLY",
            )
        row = self.usage.report()["recent"][0]
        self.assertEqual(row["request_bytes"], len(captured[0].data))
        self.assertEqual(row["input_tokens"], 21)
        self.assertGreater(row["duration_ms"], 0)
        with (
            provider.observe_requests(self.usage.recorder("mira", "dialogue")),
            patch(
                "roleweaver.provider.open_url",
                side_effect=HTTPError(
                    "https://secret.invalid", 429, "PRIVATE_ERROR", {}, None
                ),
            ),
        ):
            with self.assertRaises(HTTPError):
                provider.reply(CONFIG, profile, [], [])
        report = self.usage.report()
        self.assertEqual(report["recent"][0]["http_status"], 429)
        self.assertNotIn("PRIVATE_", json.dumps(report))
        self.assertNotIn(b"PRIVATE_", self.path.read_bytes())

    def test_usage_is_kept_when_provider_content_is_invalid(self):
        data = {"usage": {"prompt_tokens": 10, "completion_tokens": 2}, "choices": []}
        with (
            provider.observe_requests(self.usage.recorder("mira", "dialogue")),
            patch(
                "roleweaver.provider.open_url",
                return_value=Response(json.dumps(data).encode()),
            ),
        ):
            with self.assertRaises(IndexError):
                provider.reply(CONFIG, DEFAULT_NPC, [], [])
        row = self.usage.report()["recent"][0]
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["input_tokens"], 10)

    def test_offline_and_preflight_rejections_are_not_requests(self):
        with provider.observe_requests(self.usage.recorder("mira", "dialogue")):
            provider.reply({"provider": "offline"}, DEFAULT_NPC, [], [])
            with self.assertRaises(ValueError):
                provider.reply(
                    dict(CONFIG, base_url="http://remote.invalid"), DEFAULT_NPC, [], []
                )
        self.assertEqual(self.usage.report()["summary"]["requests"], 0)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Service(Path(self.temp.name), dict(CONFIG))
        self.store = self.app.store

    def tearDown(self):
        self.app.pool.shutdown(wait=True)
        self.store.db.close()
        self.temp.cleanup()

    def test_inspector_uses_audience_rules_and_hides_excluded_text(self):
        self.store.save(dict(DEFAULT_NPC, id="orren", name="Orren"))
        self.store.save_world_document(
            dict(id="public_doc", title="Public", text="Known fact", active=True)
        )
        self.store.save_world_document(
            dict(id="hidden_doc", title="Hidden", text="HIDDEN_DOC", active=False)
        )
        for id, audience, target, active in [
            ("public", "public", "", True),
            ("dm", "dm", "", True),
            ("other", "npc", "orren", True),
            ("inactive", "npc", "mira", False),
            ("own", "npc", "mira", True),
        ]:
            self.store.save_access_lore(
                dict(
                    id=id,
                    title=id,
                    text=id + "_TEXT",
                    audience=audience,
                    target=target,
                    disclosure="",
                    active=active,
                )
            )
        d = self.app.knowledge("mira")
        included = {r["id"] for r in d["access_lore"] if r["available"]}
        self.assertEqual(included, {"public", "own"})
        for secret in ("HIDDEN_DOC", "dm_TEXT", "other_TEXT", "inactive_TEXT"):
            self.assertNotIn(secret, json.dumps(d))

    def test_player_isolation_and_real_context_limits(self):
        for i in range(35):
            self.store.add_memory("mira", "a", "Memory " + str(i))
        self.store.add_memory("mira", "", "Shared fact")
        self.store.add_memory("mira", "b", "OTHER_PLAYER_SECRET")
        for i in range(20):
            self.store.message("mira", "a", "player", "Statement " + str(i))
        self.store.message("mira", "b", "player", "OTHER_HISTORY")
        d = self.app.knowledge("mira", "a")
        self.assertEqual(len(d["memories"]), 30)
        self.assertEqual(d["memory_total"], 36)
        self.assertEqual(len(d["history"]), 16)
        self.assertEqual(d["history"][0]["text"], "Statement 4")
        self.assertNotIn("OTHER_PLAYER_SECRET", json.dumps(d))
        self.assertNotIn("OTHER_HISTORY", json.dumps(d))
        shared = self.app.knowledge("mira")
        self.assertEqual(len(shared["memories"]), 1)
        self.assertEqual(shared["history"], [])
        with self.assertRaises(ValueError):
            self.app.knowledge("mira", "unknown")

    def test_memory_correction_is_scoped_and_invalidates_pending_generation(self):
        self.store.save(dict(DEFAULT_NPC, id="orren", name="Orren"))
        self.store.add_memory("mira", "", "wrong fact")
        id = self.store.memories("mira")[0]["id"]
        with self.assertRaises(ValueError):
            self.app.edit_memory("orren", id, "wrong NPC edit")
        self.app.edit_memory("mira", id, "correct fact")
        self.assertEqual(self.store.memories("mira")[0]["text"], "correct fact")
        self.assertEqual(self.app.generations["mira"], 1)
        with self.assertRaises(ValueError):
            self.app.edit_memory("mira", id, "")

    def test_service_tracks_dialogue_and_both_safeguard_requests(self):
        self.app.safeguard_policy = safeguards.settings()
        self.app.safeguard_policy["levels"]["profanity"] = "high"
        self.app.states["mira"] = dict(mode="auto", session="test", epoch=1)
        self.store.message("mira", "a", "player", "Hello")

        def response(request, **kwargs):
            prompt = json.loads(request.data)["messages"][0]["content"]
            text = (
                json.dumps(
                    dict(
                        scores=dict(profanity=0, hate=0, violence=0, sensitive=0),
                        lore="not_applicable",
                    )
                )
                if "You assess" in prompt
                else "Hello, traveler."
            )
            return Response(
                json.dumps(
                    {
                        "choices": [{"message": {"content": text}}],
                        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
                    }
                ).encode()
            )

        with (
            patch("roleweaver.provider.open_url", side_effect=response),
            patch.object(self.app, "command"),
        ):
            self.app.generate(
                "mira",
                "a",
                self.store.get("mira"),
                0,
                dict(session="test", epoch=1),
                "player-object",
                speech="Hello",
            )
        report = self.app.usage.report()
        self.assertEqual(report["summary"]["requests"], 3)
        self.assertEqual(
            {r["phase"] for r in report["recent"]},
            {"dialogue", "input_review", "output_review"},
        )


if __name__ == "__main__":
    unittest.main()
