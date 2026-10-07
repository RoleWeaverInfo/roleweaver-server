"""Portable password controls must not expose credentials or affect a PW install."""

from email.message import Message
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from roleweaver.dashboard_auth import DashboardAuth, credential_path
from roleweaver.portable_demo import change_password, settings_path
import test_recovery_http as recovery_fixture


class PortablePasswordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.json"
        self.config.write_text("{}")
        self.path = self.root / "settings.json"
        self.path.write_text(
            json.dumps(dict(id="qemu_demo", dm_password="roleweaver", web_port=8747))
        )
        self.auth = DashboardAuth(self.config, 8747)

    def change(self, kind, password, current="roleweaver"):
        return change_password(
            self.auth,
            self.config,
            self.path,
            dict(current_password=current, kind=kind, password=password),
        )

    def test_only_explicit_portable_installation_enables_route(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(settings_path(self.config))
        with patch.dict(os.environ, ROLEWEAVER_PORTABLE_SETTINGS=str(self.path)):
            self.assertEqual(settings_path(self.config), self.path)
            self.path.write_text('{"id":"production_world"}')
            self.assertIsNone(settings_path(self.config))
        outside = self.root / "other.json"
        outside.write_text('{"id":"qemu_demo"}')
        with patch.dict(os.environ, ROLEWEAVER_PORTABLE_SETTINGS=str(outside)):
            self.assertIsNone(settings_path(self.config))

    def test_dashboard_rotation_revokes_old_session_and_returns_working_session(self):
        previous = self.auth.login("roleweaver")
        result, token = self.change("dashboard", "fixture-new-password")
        self.assertFalse(result["restart_required"])
        headers = Message()
        headers["Cookie"] = self.auth.cookie + "=" + previous
        self.assertFalse(self.auth.authenticated(headers))
        headers.replace_header("Cookie", self.auth.cookie + "=" + token)
        self.assertTrue(self.auth.authenticated(headers))
        self.assertNotIn(
            "fixture-new-password", credential_path(self.config).read_text()
        )
        self.assertEqual(json.loads(self.path.read_text())["dm_password"], "roleweaver")

    def test_dm_password_preserves_other_settings_and_requires_next_start(self):
        result, _ = self.change("dm", "fixture-DM-123")
        self.assertTrue(result["restart_required"])
        value = json.loads(self.path.read_text())
        self.assertEqual(value["dm_password"], "fixture-DM-123")
        self.assertEqual(value["web_port"], 8747)
        self.assertIsNotNone(self.auth.login("roleweaver"))
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_wrong_current_password_and_invalid_new_password_leave_files_unchanged(
        self,
    ):
        original = self.path.read_bytes(), credential_path(self.config).read_bytes()
        with self.assertRaises(PermissionError):
            self.change("dm", "fixture-valid-dm", current="incorrect")
        for kind, password in (
            ("dm", "short"),
            ("dm", "contains spaces"),
            ("dm", "x" * 33),
            ("dashboard", "short"),
        ):
            with (
                self.subTest(kind=kind, password=password),
                self.assertRaises(ValueError),
            ):
                self.change(kind, password)
        self.assertEqual(
            original,
            (self.path.read_bytes(), credential_path(self.config).read_bytes()),
        )


class PortableHTTPTests(unittest.TestCase):
    # Reuse the isolated Redis/process harness, without inheriting its tests.
    setUp = recovery_fixture.RecoveryHTTPTests.setUp
    tearDown = recovery_fixture.RecoveryHTTPTests.tearDown
    start = recovery_fixture.RecoveryHTTPTests.start
    halt = recovery_fixture.RecoveryHTTPTests.halt
    request = recovery_fixture.RecoveryHTTPTests.request

    def test_password_route_is_authenticated_and_rejects_cross_origin_changes(self):
        path = self.root / "settings.json"
        path.write_text('{"id":"qemu_demo","dm_password":"roleweaver"}')
        with patch.dict(os.environ, ROLEWEAVER_PORTABLE_SETTINGS=str(path)):
            self.start(authenticate=False)
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/demo-password")
        self.assertEqual(cm.exception.code, 401)
        self.request("/api/login", dict(password="roleweaver"))
        self.assertTrue(self.request("/api/demo-password")["available"])
        body = dict(current_password="roleweaver", kind="dm", password="fixture-dm")
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/demo-password", body, origin="https://outside.invalid")
        self.assertEqual(cm.exception.code, 403)
        self.assertEqual(json.loads(path.read_text())["dm_password"], "roleweaver")
        self.assertTrue(self.request("/api/demo-password", body)["restart_required"])
        self.assertEqual(json.loads(path.read_text())["dm_password"], "fixture-dm")
        old_cookie = self.cookie
        body.update(kind="dashboard", password="fixture-dashboard")
        self.assertFalse(self.request("/api/demo-password", body)["restart_required"])
        new_cookie = self.cookie
        self.assertTrue(self.request("/api/demo-password")["available"])
        self.cookie = old_cookie
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/demo-password")
        self.assertEqual(cm.exception.code, 401)
        self.cookie = new_cookie

    def test_normal_server_does_not_enable_password_editor(self):
        with patch.dict(os.environ, ROLEWEAVER_PORTABLE_SETTINGS=""):
            self.start()
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/demo-password")
        self.assertEqual(cm.exception.code, 404)
