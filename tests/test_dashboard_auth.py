"""Dashboard access must remain protected across recovery, restart and password reset."""

from email.message import Message
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from roleweaver.dashboard_auth import (
    DashboardAuth,
    LoginBusy,
    SESSION_SECONDS,
    credential_path,
    set_password,
    probe_headers,
)
import test_recovery_http as recovery_fixture


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / "config.json"
        self.config.write_text("{}")
        self.now = 0
        self.auth = DashboardAuth(self.config, 8743, clock=lambda: self.now)

    def headers(self, token):
        h = Message()
        h["Cookie"] = self.auth.cookie + "=" + token
        return h

    def test_hash_only_password_rotation_and_session_expiry(self):
        path = credential_path(self.config)
        if os.name != "nt":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("roleweaver", path.read_text())
        self.assertIsNone(self.auth.login("wrong"))
        token = self.auth.login("roleweaver")
        self.assertTrue(self.auth.authenticated(self.headers(token)))
        self.now = SESSION_SECONDS
        self.assertFalse(self.auth.authenticated(self.headers(token)))
        token = self.auth.login("roleweaver")
        set_password(self.config, "different fixture password")
        self.assertFalse(self.auth.authenticated(self.headers(token)))
        self.assertIsNone(self.auth.login("roleweaver"))
        self.assertTrue(self.auth.login("different fixture password"))
        self.assertNotIn("different fixture password", path.read_text())

    def test_restart_and_logout_revoke_sessions_without_resetting_password(self):
        set_password(self.config, "changed fixture password")
        token = self.auth.login("changed fixture password")
        self.auth.logout(self.headers(token))
        self.assertFalse(self.auth.authenticated(self.headers(token)))
        token = self.auth.login("changed fixture password")
        restarted = DashboardAuth(self.config, 8743)
        self.assertFalse(restarted.authenticated(self.headers(token)))
        self.assertIsNone(restarted.login("roleweaver"))
        self.assertTrue(restarted.login("changed fixture password"))

    def test_login_work_is_bounded_and_recovers(self):
        for _ in range(10):
            self.assertIsNone(self.auth.login("incorrect"))
        with self.assertRaises(LoginBusy):
            self.auth.login("roleweaver")
        self.now = 60
        self.assertTrue(self.auth.login("roleweaver"))
        self.auth.verifying.acquire()
        try:
            with self.assertRaises(LoginBusy):
                self.auth.login("roleweaver")
        finally:
            self.auth.verifying.release()

    def test_missing_corrupt_credentials_fail_closed(self):
        token = self.auth.login("roleweaver")
        path = credential_path(self.config)
        for content in ("{", "[]", '{"digest":"PRIVATE_SECRET"}'):
            path.write_text(content)
            with self.assertRaisesRegex(ValueError, "credentials unavailable") as error:
                self.auth.authenticated(self.headers(token))
            self.assertNotIn("PRIVATE_SECRET", str(error.exception))
        path.unlink()
        with self.assertRaises(ValueError):
            self.auth.authenticated(self.headers(token))
        set_password(self.config, "repaired fixture password")
        self.assertFalse(self.auth.authenticated(self.headers(token)))
        self.assertTrue(self.auth.login("repaired fixture password"))

    def test_probe_token_is_read_only_and_revoked_on_reset(self):
        h = Message()
        for key, value in probe_headers(self.config).items():
            h[key] = value
        self.assertTrue(self.auth.probe(h, "GET", "/api/health"))
        for method, path in (
            ("POST", "/api/health"),
            ("GET", "/api/backup"),
            ("GET", "/api/databases"),
            ("POST", "/api/llm"),
        ):
            self.assertFalse(self.auth.probe(h, method, path))
        self.assertFalse(self.auth.authenticated(h))
        set_password(self.config, "new fixture password")
        self.assertFalse(self.auth.probe(h, "GET", "/api/health"))


class LoginHTTPTests(unittest.TestCase):
    setUp = recovery_fixture.RecoveryHTTPTests.setUp
    tearDown = recovery_fixture.RecoveryHTTPTests.tearDown
    start = recovery_fixture.RecoveryHTTPTests.start
    halt = recovery_fixture.RecoveryHTTPTests.halt
    request = recovery_fixture.RecoveryHTTPTests.request

    def test_unauthenticated_pages_and_all_api_groups_are_protected(self):
        self.start(authenticate=False)
        for path in ("/", "/health", "/recovery"):
            self.assertIn(b"Dashboard sign in", self.request(path))
        for path in (
            "/api/state",
            "/api/health",
            "/api/support-report",
            "/api/databases",
            "/api/databases/download?name=fixture.zip",
            "/api/backup",
            "/api/llm",
            "/api/companions",
            "/api/session",
            "/api/translations",
        ):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.request(path)
            self.assertEqual(error.exception.code, 401)
        with self.assertRaises(HTTPError) as error:
            self.request("/api/databases/create", {})
        self.assertEqual(error.exception.code, 401)
        self.assertFalse(
            self.request("/api/login", {"password": "roleweaver"}).get("password")
        )
        self.assertIn("npcs", self.request("/api/state"))

    def test_cookie_logout_and_password_reset(self):
        self.start(authenticate=False)
        request = Request(
            f"http://127.0.0.1:{self.port}/api/login",
            data=b'{"password":"roleweaver"}',
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn("roleweaver", cookie)
        self.cookie = cookie.split(";", 1)[0]
        saved = self.cookie
        self.request("/api/logout", {})
        self.cookie = saved
        with self.assertRaises(HTTPError) as error:
            self.request("/api/state")
        self.assertEqual(error.exception.code, 401)
        self.request("/api/login", {"password": "roleweaver"})
        set_password(self.config, "changed fixture password")
        with self.assertRaises(HTTPError) as error:
            self.request("/api/state")
        self.assertEqual(error.exception.code, 401)
        self.request("/api/login", {"password": "changed fixture password"})
        self.assertTrue(self.request("/api/session")["authenticated"])

    def test_wrong_password_cross_origin_and_non_json_login_rejected(self):
        self.start(authenticate=False)
        for body, origin, kind, expected in (
            ({"password": "wrong"}, None, "application/json", 401),
            (
                {"password": "roleweaver"},
                "https://outside.invalid",
                "application/json",
                403,
            ),
            (b"password=roleweaver", None, "application/x-www-form-urlencoded", 400),
            ([], None, "application/json", 400),
        ):
            with self.subTest(body=body), self.assertRaises(HTTPError) as error:
                self.request("/api/login", body, origin, kind)
            self.assertEqual(error.exception.code, expected)
        self.assertEqual(self.cookie, "")

    def test_server_probe_cannot_download_backups_or_mutate_world(self):
        self.start(authenticate=False)
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from manage_installation import health

        value = health(self.port, timeout=3, config_path=self.config)
        self.assertEqual(value["components"]["companion"]["state"], "healthy")
        headers = probe_headers(self.config)
        for path, body, expected in (
            ("/api/health", None, 200),
            ("/api/databases", None, 401),
            ("/api/llm-test", b"{}", 401),
        ):
            request = Request(
                f"http://127.0.0.1:{self.port}" + path, data=body, headers=headers
            )
            if expected == 200:
                with urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
            else:
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=5)
                self.assertEqual(error.exception.code, expected)

    def test_corrupt_database_recovery_remains_password_protected(self):
        (self.root / "data").mkdir()
        (self.root / "data/roleweaver.sqlite3").write_bytes(b"corrupt")
        self.start(authenticate=False)
        self.assertIn(b"Dashboard sign in", self.request("/recovery"))
        self.request("/api/login", {"password": "roleweaver"})
        self.assertIn(b"Database &amp; Recovery", self.request("/recovery"))
        self.assertFalse(self.request("/api/databases")["available"])
