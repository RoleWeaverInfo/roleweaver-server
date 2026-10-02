import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "installer", Path(__file__).resolve().parents[1] / "tools/install_companion.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@unittest.skipUnless(sys.platform == "linux", "Linux installer")
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.args = SimpleNamespace(
            world_id="install_probe",
            target=Path(self.temp.name) / "companion space",
            port=port,
            redis_port=6379,
            redis_prefix=None,
        )

    def tearDown(self):
        self.temp.cleanup()

    def install(self):
        with (
            patch.object(
                installer.subprocess, "run", return_value=SimpleNamespace(returncode=1)
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            installer.install(self.args)

    def test_fresh_install_and_upgrade_preserve_config(self):
        self.install()
        root = self.args.target
        first = (root / "current").resolve()
        config = json.loads((root / "config.json").read_text())
        config["model"] = "preserve-me"
        (root / "config.json").write_text(json.dumps(config))
        (root / "provider.env").write_text("ROLEWEAVER_API_KEY=test-private-value")
        self.install()
        self.assertNotEqual((root / "current").resolve(), first)
        self.assertEqual((root / "previous").resolve(), first)
        self.assertEqual(
            json.loads((root / "config.json").read_text())["model"], "preserve-me"
        )
        self.assertEqual(
            (root / "provider.env").read_text(), "ROLEWEAVER_API_KEY=test-private-value"
        )
        self.assertEqual((root / "provider.env").stat().st_mode & 0o777, 0o600)

    def test_other_world_refused(self):
        self.install()
        self.args.world_id = "different"
        with self.assertRaises(ValueError):
            self.install()

    def test_busy_port_refused_before_install(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", self.args.port))
            sock.listen()
            with self.assertRaises(ValueError):
                self.install()
        self.assertFalse(self.args.target.exists())

    def test_generated_unit_is_accepted_by_systemd(self):
        if not shutil.which("systemd-analyze"):
            self.skipTest("systemd-analyze unavailable")
        self.install()
        unit = self.args.target / "roleweaver-install_probe.service"
        result = subprocess.run(
            ["systemd-analyze", "verify", str(unit)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_recent_http_connection_does_not_block_stopped_service_install(self):
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", self.args.port))
            server.listen()
            with socket.create_connection(("127.0.0.1", self.args.port)) as client:
                connection, _ = server.accept()
                connection.shutdown(socket.SHUT_WR)
                connection.close()
                self.assertEqual(client.recv(1), b"")
        self.install()
        self.assertTrue((self.args.target / "current").exists())

    def test_running_service_refused(self):
        with patch.object(
            installer.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ):
            with self.assertRaises(ValueError):
                installer.install(self.args)
        self.assertFalse(self.args.target.exists())
