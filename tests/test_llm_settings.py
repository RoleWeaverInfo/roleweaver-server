import copy, json, os, tempfile, unittest, urllib.error
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from roleweaver.llm_settings import Settings, endpoint, NoRedirect
from roleweaver.service import Service
from roleweaver import provider
from roleweaver.store import DEFAULT_NPC
from roleweaver.usage import Usage
from test_insights import Response, event


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = dict(
            provider="openai-compatible",
            base_url="https://api.openai.com/v1",
            model="original-model",
            api_key_env="TEST_OLD_KEY",
        )
        self.s = Settings(self.root, self.base)

    def tearDown(self):
        self.temp.cleanup()

    def body(self, kind="openai", **extra):
        return dict(
            service=kind,
            model="test-model",
            api_key="SECRET_TEST_VALUE",
            key_action="replace",
            revision=self.s.data["revision"],
            **extra,
        )

    def test_private_persistence_and_redacted_status(self):
        self.s.save(self.body())
        self.assertNotIn("SECRET_TEST_VALUE", json.dumps(self.s.status()))
        self.assertEqual(
            Settings(self.root, self.base).runtime()["_api_key"], "SECRET_TEST_VALUE"
        )
        if os.name != "nt":
            self.assertEqual(self.s.path.stat().st_mode & 0o777, 0o600)

    def test_provider_keys_are_separate(self):
        self.s.save(self.body())
        c = self.s.runtime("gemini", self.s.data["profiles"]["gemini"])
        self.assertEqual(c["_api_key"], "")
        with patch.dict(os.environ, TEST_OLD_KEY="old-secret"):
            c = self.s.runtime("lmstudio", self.s.data["profiles"]["lmstudio"])
            self.assertEqual(c["_api_key"], "")

    def test_original_environment_key_is_not_copied_to_disk(self):
        with patch.dict(os.environ, TEST_OLD_KEY="env-secret"):
            self.s.save(dict(self.body(), key_action="keep", api_key=""))
            self.assertEqual(self.s.runtime()["_api_key"], "env-secret")
            self.assertNotIn("env-secret", self.s.path.read_text())

    def test_explicit_removal_suppresses_environment_fallback(self):
        with patch.dict(os.environ, TEST_OLD_KEY="env-secret"):
            self.s.save(dict(self.body(), key_action="clear", api_key=""))
            self.assertEqual(self.s.runtime()["_api_key"], "")
            with self.assertRaises(ValueError):
                self.s.probe(dict(self.body(), key_action="keep", api_key=""))

    def test_lmstudio_url_and_token_scope(self):
        self.s.save(self.body("lmstudio", base_url="http://192.168.1.20:1234"))
        k, p = self.s.candidate(
            dict(
                self.body("lmstudio", base_url="http://192.168.1.21:1234"),
                key_action="keep",
                api_key="",
            )
        )
        self.assertEqual(self.s.key(p), "")
        self.assertEqual(p["base_url"], "http://192.168.1.21:1234/v1")

    def test_endpoint_validation(self):
        for value in (
            "http://8.8.8.8:1234/v1",
            "http://169.254.169.254/v1",
            "http://user:pass@localhost:1234/v1",
            "http://localhost:1234/v1?key=secret",
            "http://localhost:1234/evil",
            "file:///etc/passwd",
            "http://bad.example/v1",
        ):
            with self.assertRaises(ValueError):
                endpoint("lmstudio", value)
        for value in (
            "http://localhost:1234/v1",
            "http://127.0.0.1:1234/v1",
            "http://192.168.167.1:1234/v1",
            "http://[::1]:1234/v1",
        ):
            self.assertEqual(endpoint("lmstudio", value), value)
        self.assertEqual(
            endpoint("openai", "https://evil.invalid"), "https://api.openai.com/v1"
        )

    def test_stale_and_failed_save_preserve_active_settings(self):
        old = copy.deepcopy(self.s.data)
        with self.assertRaises(ValueError):
            self.s.save(dict(self.body(), revision="stale"))
        with patch("os.replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.s.save(self.body())
        self.assertEqual(self.s.data, old)
        self.assertFalse(list(self.root.glob(".llm-*")))

    def test_model_list_uses_selected_credentials_without_saving(self):
        with patch(
            "roleweaver.llm_settings.open_url",
            return_value=Response(b'{"data":[{"id":"b"},{"id":"a"}]}'),
        ) as request:
            result = self.s.probe(self.body("gemini"), True)
        self.assertEqual(result["models"], ["a", "b"])
        self.assertFalse(self.s.path.exists())
        req = request.call_args.args[0]
        self.assertEqual(
            req.full_url,
            "https://generativelanguage.googleapis.com/v1beta/openai/models",
        )
        self.assertEqual(req.get_header("Authorization"), "Bearer SECRET_TEST_VALUE")

    def test_test_connection_validates_json_and_does_not_save(self):
        data = {"choices": [{"message": {"content": '{"speech":"Hello","action":""}'}}]}
        with patch(
            "roleweaver.provider.open_url",
            return_value=Response(json.dumps(data).encode()),
        ) as request:
            self.assertTrue(self.s.probe(self.body())["ok"])
        self.assertFalse(self.s.path.exists())
        body = json.loads(request.call_args.args[0].data)
        self.assertIn("max_completion_tokens", body)
        with patch(
            "roleweaver.provider.open_url",
            return_value=Response(b'{"choices":[{"message":{"content":"Not JSON"}}]}'),
        ):
            with self.assertRaises(ValueError):
                self.s.probe(self.body())

    def test_errors_never_echo_provider_credentials(self):
        with patch(
            "roleweaver.llm_settings.open_url",
            side_effect=urllib.error.HTTPError(
                "https://SECRET_URL", 401, "SECRET_TEXT", {}, None
            ),
        ):
            with self.assertRaises(ValueError) as caught:
                self.s.probe(self.body(), True)
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertIn("401", str(caught.exception))

    def test_local_http_model_list_and_json_reply(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        captured = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                captured.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"local-test"}]}')

            def do_POST(self):
                captured.append(self.path)
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                captured.append(body["model"])
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "choices": [
                                {
                                    "message": {
                                        "content": json.dumps(
                                            dict(speech="Hello", action="")
                                        )
                                    }
                                }
                            ]
                        }
                    ).encode()
                )

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            body = dict(
                self.body(
                    "lmstudio", base_url=f"http://127.0.0.1:{server.server_port}/v1"
                ),
                api_key="",
                key_action="keep",
            )
            self.assertEqual(self.s.probe(body, True)["models"], ["local-test"])
            self.assertTrue(self.s.probe(body)["ok"])
            self.assertEqual(
                captured, ["/v1/models", "/v1/chat/completions", "test-model"]
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_no_change_to_original_runtime_before_first_save(self):
        self.assertEqual(self.s.runtime(), self.base)

    def test_redirects_refused(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(
                None, None, 302, "", {}, "https://evil.invalid"
            )

    def test_dialogue_and_review_use_gemini_and_local_credentials(self):
        for kind, parameter in [
            ("gemini", "max_tokens"),
            ("lmstudio", "max_tokens"),
            ("openai", "max_completion_tokens"),
        ]:
            k, p = self.s.candidate(self.body(kind))
            c = self.s.runtime(k, p)
            with patch(
                "roleweaver.provider.open_url",
                return_value=Response(b'{"choices":[{"message":{"content":"Hello"}}]}'),
            ) as req:
                self.assertEqual(provider.reply(c, DEFAULT_NPC, [], []), "Hello")
            self.assertIn(parameter, json.loads(req.call_args.args[0].data))
            self.assertEqual(
                req.call_args.args[0].get_header("Authorization"),
                "Bearer SECRET_TEST_VALUE",
            )

    def test_backup_excludes_keys_and_settings(self):
        app = Service(self.root, dict(self.base))
        try:
            app.busy.add("mira")
            app.generations["mira"] = 3
            app.save_llm(dict(self.body(), revision=app.llm.data["revision"]))
            self.assertEqual(app.generations["mira"], 4)
            self.assertNotIn("SECRET_TEST_VALUE", json.dumps(app.backup_data()))
            self.assertNotIn("SECRET_TEST_VALUE", json.dumps(app.snapshot()))
            self.assertEqual(app.config["model"], "test-model")
        finally:
            app.pool.shutdown()
            app.store.db.close()

    def test_usage_recorder_keeps_original_provider_after_switch(self):
        u = Usage(self.root / "usage.sqlite3", self.base)
        record = u.recorder("mira", "dialogue", self.base)
        original = u.provider
        u.configure(dict(self.base, base_url="http://127.0.0.1:1234/v1", model="local"))
        record(event())
        row = u.report()["recent"][0]
        self.assertEqual(row["model"], "original-model")
        import sqlite3

        with closing(sqlite3.connect(u.path)) as db:
            self.assertEqual(
                db.execute("SELECT provider FROM requests").fetchone()[0], original
            )


if __name__ == "__main__":
    unittest.main()
