import json, tempfile, unittest, urllib.error
from pathlib import Path
from unittest.mock import patch
from roleweaver import provider
from roleweaver.llm_settings import ENDPOINTS, Settings
from roleweaver.usage import Usage
from test_insights import Response


def error(code):
    return urllib.error.HTTPError("https://provider.invalid", code, "busy", {}, None)


class GeminiFallbackTests(unittest.TestCase):
    def setUp(self):
        provider._gemini_preferred.clear()
        self.addCleanup(provider._gemini_preferred.clear)
        provider._gemini_cooldowns.clear()
        self.addCleanup(provider._gemini_cooldowns.clear)
        self.c = dict(
            llm_service="gemini",
            gemini_fallback_on_busy=True,
            model="gemini-3.7-flash",
            base_url=ENDPOINTS["gemini"],
        )
        self.body = json.dumps(
            dict(model=self.c["model"], messages=[dict(role="user", content="hello")])
        ).encode()

    def run_request(self):
        return provider.complete(
            ENDPOINTS["gemini"] + "/chat/completions",
            self.body,
            {"Authorization": "Bearer private-test"},
            30,
            10000,
            lambda d: d["answer"],
            config=self.c,
        )

    def test_busy_switches_models_and_preserves_prompt_and_key(self):
        events = []
        with (
            patch(
                "roleweaver.provider.open_url",
                side_effect=[error(503), Response(b'{"answer":"ok"}')],
            ) as call,
            provider.observe_requests(events.append),
        ):
            self.assertEqual(self.run_request(), "ok")
        bodies = [json.loads(c.args[0].data) for c in call.call_args_list]
        self.assertEqual(
            [b["model"] for b in bodies], ["gemini-3.7-flash", "gemini-3.6-flash"]
        )
        self.assertEqual(bodies[0]["messages"], bodies[1]["messages"])
        self.assertEqual(
            [e["model"] for e in events], ["gemini-3.7-flash", "gemini-3.6-flash"]
        )
        self.assertEqual([e["http_status"] for e in events][0], 503)
        self.assertEqual(
            call.call_args_list[1].args[0].get_header("Authorization"),
            "Bearer private-test",
        )

    def test_all_busy_is_bounded_and_next_request_returns_to_primary(self):
        with patch(
            "roleweaver.provider.open_url",
            side_effect=[
                error(503),
                error(503),
                error(503),
                Response(b'{"answer":"ok"}'),
            ],
        ) as call:
            with self.assertRaises(urllib.error.HTTPError):
                self.run_request()
            self.assertEqual(call.call_count, 3)
            self.assertEqual(self.run_request(), "ok")
        self.assertEqual(
            json.loads(call.call_args_list[3].args[0].data)["model"], "gemini-3.7-flash"
        )

    def test_prefixed_model_id_is_supported(self):
        self.body = json.dumps(
            dict(model="models/gemini-3.7-flash", messages=[])
        ).encode()
        with patch(
            "roleweaver.provider.open_url",
            side_effect=[error(503), Response(b'{"answer":"ok"}')],
        ) as call:
            self.assertEqual(self.run_request(), "ok")
        self.assertEqual(
            json.loads(call.call_args.args[0].data)["model"], "gemini-3.6-flash"
        )

    def test_timeouts_advance_with_reserved_time(self):
        for failure in (
            TimeoutError("slow"),
            urllib.error.URLError(TimeoutError("slow")),
            error(408),
            error(504),
        ):
            provider._gemini_preferred.clear()
            provider._gemini_cooldowns.clear()
            with patch(
                "roleweaver.provider.open_url",
                side_effect=[failure, Response(b'{"answer":"ok"}')],
            ) as call:
                self.assertEqual(self.run_request(), "ok")
            self.assertLessEqual(call.call_args_list[0].kwargs["timeout"], 10)
            self.assertGreater(call.call_args_list[1].kwargs["timeout"], 10)
            self.assertEqual(
                json.loads(call.call_args_list[1].args[0].data)["model"],
                "gemini-3.6-flash",
            )

    def test_response_read_timeout_advances(self):
        class SlowResponse(Response):
            def read(self, *args):
                raise TimeoutError("response stalled")

        with patch(
            "roleweaver.provider.open_url",
            side_effect=[SlowResponse(b""), Response(b'{"answer":"ok"}')],
        ):
            self.assertEqual(self.run_request(), "ok")

    def test_connection_errors_other_than_timeout_do_not_switch(self):
        with patch(
            "roleweaver.provider.open_url",
            side_effect=urllib.error.URLError(ConnectionRefusedError()),
        ) as call:
            with self.assertRaises(urllib.error.URLError):
                self.run_request()
            self.assertEqual(call.call_count, 1)

    def test_all_timeouts_are_bounded(self):
        with patch(
            "roleweaver.provider.open_url", side_effect=TimeoutError("slow")
        ) as call:
            with self.assertRaises(TimeoutError):
                self.run_request()
            self.assertEqual(call.call_count, 3)

    def test_cooldown_skips_and_expires_with_prefixed_primary(self):
        self.body = json.dumps(
            dict(model="models/gemini-3.7-flash", messages=[])
        ).encode()
        with (
            patch("roleweaver.provider.time.monotonic", return_value=100),
            patch(
                "roleweaver.provider.open_url",
                side_effect=[
                    TimeoutError(),
                    Response(b'{"answer":"ok"}'),
                    Response(b'{"answer":"ok"}'),
                ],
            ) as call,
        ):
            self.run_request()
            self.run_request()
            self.assertEqual(
                json.loads(call.call_args.args[0].data)["model"], "gemini-3.6-flash"
            )
        with (
            patch("roleweaver.provider.time.monotonic", return_value=221),
            patch(
                "roleweaver.provider.open_url",
                return_value=Response(b'{"answer":"ok"}'),
            ) as call,
        ):
            self.run_request()
            self.assertEqual(
                json.loads(call.call_args.args[0].data)["model"], "gemini-3.6-flash"
            )

    def test_next_request_reaches_new_models_and_all_cooling_fails_fast(self):
        with patch("roleweaver.provider.open_url", side_effect=TimeoutError()) as call:
            for _ in range(3):
                with self.assertRaises(TimeoutError):
                    self.run_request()
            self.assertEqual(call.call_count, 6)
            self.assertEqual(
                [json.loads(c.args[0].data)["model"] for c in call.call_args_list][-3:],
                ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"],
            )

    def test_new_models_can_be_selected(self):
        with tempfile.TemporaryDirectory() as d:
            s = Settings(Path(d), dict(provider="offline"))
            for model in (
                "gemini-3.8-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
            ):
                k, p = s.candidate(
                    dict(service="gemini", model=model, fallback_on_busy=True)
                )
                self.assertTrue(s.runtime(k, p)["gemini_fallback_on_busy"])

    def test_structured_review_requested_and_invalid_json_rejected(self):
        c = dict(self.c, provider="openai-compatible")
        policy = dict(topics=[], lore_check=True)
        valid = json.dumps(
            dict(
                scores=dict(profanity=0, hate=0, violence=0, sensitive=0),
                lore="not_applicable",
            )
        )
        response = Response(
            json.dumps({"choices": [{"message": {"content": valid}}]}).encode()
        )
        with patch("roleweaver.provider.open_url", return_value=response) as call:
            self.assertEqual(
                provider.review(c, "Hello", "input", policy, {})["lore"],
                "not_applicable",
            )
            fmt = json.loads(call.call_args.args[0].data)["response_format"]
            self.assertEqual(fmt["type"], "json_schema")
            self.assertEqual(
                fmt["json_schema"]["schema"]["required"], ["scores", "lore"]
            )
        with patch(
            "roleweaver.provider.open_url",
            return_value=Response(b'{"choices":[{"message":{"content":"not JSON"}}]}'),
        ) as call:
            with self.assertRaises(json.JSONDecodeError):
                provider.review(c, "Hello", "input", policy, {})
            self.assertEqual(call.call_count, 1)
        self.assertEqual(provider.json_format(dict(llm_service="lmstudio")), {})
        self.assertEqual(
            provider.json_format(c)["response_format"]["json_schema"]["schema"][
                "required"
            ],
            ["speech", "action"],
        )

    def test_success_is_sticky_until_failure(self):
        with patch(
            "roleweaver.provider.open_url",
            side_effect=[
                error(503),
                Response(b'{"answer":"ok"}'),
                Response(b'{"answer":"ok"}'),
                error(503),
                Response(b'{"answer":"ok"}'),
                Response(b'{"answer":"ok"}'),
            ],
        ) as call:
            for _ in range(4):
                self.run_request()
        self.assertEqual(
            [json.loads(c.args[0].data)["model"] for c in call.call_args_list],
            [
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.6-flash",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.7-flash",
            ],
        )

    def test_invalid_response_clears_preference_without_retry(self):
        with patch(
            "roleweaver.provider.open_url",
            side_effect=[error(503), Response(b'{"answer":"ok"}'), Response(b"bad")],
        ):
            self.run_request()
            with self.assertRaises(json.JSONDecodeError):
                self.run_request()
        self.assertEqual(provider._gemini_preferred, {})

    def test_different_selected_model_does_not_reuse_preference(self):
        with patch(
            "roleweaver.provider.open_url",
            side_effect=[
                error(503),
                Response(b'{"answer":"ok"}'),
                Response(b'{"answer":"ok"}'),
            ],
        ) as call:
            self.run_request()
            self.body = json.dumps(dict(model="gemini-3.8-flash", messages=[])).encode()
            self.run_request()
        self.assertEqual(
            json.loads(call.call_args.args[0].data)["model"], "gemini-3.8-flash"
        )

    def test_non_busy_errors_never_fallback(self):
        for code in (400, 401, 403, 404, 429, 500, 502):
            with patch("roleweaver.provider.open_url", side_effect=error(code)) as call:
                with self.assertRaises(urllib.error.HTTPError):
                    self.run_request()
                self.assertEqual(call.call_count, 1)

    def test_invalid_output_does_not_fallback_or_bypass_checks(self):
        with patch(
            "roleweaver.provider.open_url", return_value=Response(b'{"bad":"format"}')
        ) as call:
            with self.assertRaises(KeyError):
                self.run_request()
            self.assertEqual(call.call_count, 1)

    def test_opt_out_and_other_providers_never_fallback(self):
        for change in (dict(gemini_fallback_on_busy=False), dict(llm_service="openai")):
            self.c.update(gemini_fallback_on_busy=True, llm_service="gemini")
            self.c.update(change)
            with patch("roleweaver.provider.open_url", side_effect=error(503)) as call:
                with self.assertRaises(urllib.error.HTTPError):
                    self.run_request()
                self.assertEqual(call.call_count, 1)

    def test_whole_request_deadline(self):
        with (
            patch("roleweaver.provider.time.monotonic", side_effect=[0, 1, 31]),
            patch("roleweaver.provider.open_url", side_effect=error(503)) as call,
        ):
            with self.assertRaises(TimeoutError):
                self.run_request()
            self.assertEqual(call.call_count, 1)

    def test_usage_tracks_actual_fallback_and_rates(self):
        with tempfile.TemporaryDirectory() as d:
            u = Usage(Path(d) / "usage.sqlite3", self.c)
            u.save_price("gemini-3.6-flash", dict(input=1, output=2, cached=None))
            response = Response(
                b'{"answer":"ok","usage":{"prompt_tokens":10,"completion_tokens":5}}'
            )
            with (
                provider.observe_requests(u.recorder("mira", "dialogue", self.c)),
                patch(
                    "roleweaver.provider.open_url", side_effect=[error(503), response]
                ),
            ):
                self.run_request()
            report = u.report()
            self.assertEqual(report["summary"]["requests"], 2)
            rows = {row["model"]: row for row in report["recent"]}
            self.assertEqual(rows["gemini-3.7-flash"]["status"], "error")
            self.assertAlmostEqual(rows["gemini-3.6-flash"]["cost_usd"], 0.00002)

    def test_only_reviewed_models_can_enable_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            s = Settings(Path(d), dict(provider="offline"))
            for model in ("gemini-pro", "gemini-flash-latest", "gemini-image"):
                with self.assertRaises(ValueError):
                    s.candidate(
                        dict(service="gemini", model=model, fallback_on_busy=True)
                    )
            k, p = s.candidate(
                dict(service="gemini", model="gemini-3.7-flash", fallback_on_busy=True)
            )
            self.assertTrue(s.runtime(k, p)["gemini_fallback_on_busy"])


if __name__ == "__main__":
    unittest.main()
