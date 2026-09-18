import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socket
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

    def test_running_service_refused(self):
        with patch.object(
            installer.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ):
            with self.assertRaises(ValueError):
                installer.install(self.args)
        self.assertFalse(self.args.target.exists())
