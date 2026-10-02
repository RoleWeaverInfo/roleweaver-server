"""Isolated HTTP smoke tests, including the corrupt-database recovery page."""

import json
import http.client
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RecoveryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.config = self.root / "config.json"
        # An isolated RESP endpoint lets restore clear the old game's queues
        # without contacting the developer's Redis or NWN processes.
        calls = self.redis_calls = []

        class RedisHandler(socketserver.StreamRequestHandler):
            def handle(self):
                count = int(self.rfile.readline()[1:])
                args = []
                for _ in range(count):
                    size = int(self.rfile.readline()[1:])
                    args.append(self.rfile.read(size).decode())
                    self.rfile.read(2)
                calls.append(args)
                self.wfile.write(
                    b"+PONG\r\n"
                    if args[0] == "PING"
                    else b"$-1\r\n" if args[0] == "LPOP" else b":0\r\n"
                )

        self.redis = socketserver.ThreadingTCPServer(("127.0.0.1", 0), RedisHandler)
        self.redis.daemon_threads = True
        self.redis_thread = threading.Thread(
            target=self.redis.serve_forever, daemon=True
        )
        self.redis_thread.start()
        self.config.write_text(
            json.dumps(
                dict(
                    provider="offline",
                    world_id="http_test",
                    web_port=self.port,
                    redis_port=self.redis.server_address[1],
                )
            )
        )
        self.process = None
        self.cookie = ""

    def start(self, authenticate=True, password="roleweaver"):
        self.cookie = ""
        self.process = subprocess.Popen(
            [sys.executable, "-m", "roleweaver.web", "--config", str(self.config)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            try:
                self.request("/login")
                if authenticate:
                    self.request("/api/login", {"password": password})
                return
            except URLError:
                time.sleep(0.05)
        self.fail("Recovery HTTP server did not start")

    def halt(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None

    def test_health_and_support_remain_available_with_corrupt_world(self):
        data = self.root / "data"
        data.mkdir()
        (data / "roleweaver.sqlite3").write_bytes(b"corrupt PRIVATE_WORLD")
        self.start()
        self.assertIn(b"Health &amp; Support", self.request("/health"))
        for _ in range(100):
            health = self.request("/api/health")
            if "companion" in health["components"]:
                break
            time.sleep(0.05)
        self.assertEqual(health["components"]["companion"]["state"], "error")
        self.assertEqual(health["components"]["redis"]["state"], "healthy")
        self.assertTrue(self.request("/api/support-report").startswith(b"PK"))
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/support-report", origin="https://outside.invalid")
        self.assertEqual(cm.exception.code, 403)

    def tearDown(self):
        self.halt()
        self.redis.shutdown()
        self.redis.server_close()
        self.redis_thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, origin=None, content_type="application/json"):
        headers = {}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if body is not None:
            headers["Content-Type"] = content_type
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
        if origin:
            headers["Origin"] = origin
        with urlopen(
            Request(f"http://127.0.0.1:{self.port}" + path, data=body, headers=headers),
            timeout=5,
        ) as r:
            if r.headers.get("Set-Cookie"):
                self.cookie = r.headers["Set-Cookie"].split(";", 1)[0]
            data = r.read()
            return (
                json.loads(data)
                if r.headers.get_content_type() == "application/json"
                else data
            )

    def action(self, name, body=None):
        self.request("/api/databases/" + name, body or {})
        for _ in range(200):
            job = self.request("/api/databases")["job"]
            if not job["running"]:
                self.assertFalse(job["error"], job["error"])
                return job["result"]
            time.sleep(0.02)
        self.fail("Recovery operation did not finish")

    def test_roundtrip_and_corrupt_startup(self):
        self.start()
        point = self.action("create")
        archive = self.request("/api/databases/download?name=" + point["name"])
        self.assertTrue(archive.startswith(b"PK"))
        self.assertIn(b"Database recovery", self.request("/database-recovery.js"))
        self.assertIn("npcs", self.request("/api/state"))
        preview = self.action("preview", dict(name=point["name"], scope="all"))
        result = self.action("restore", dict(token=preview["token"], game_stopped=True))
        self.assertTrue(result["restored"])
        self.assertIn(
            ["DEL", "roleweaver:v1:events", "roleweaver:v1:commands"], self.redis_calls
        )
        self.halt()
        # Destroy only this temporary test world, including any old WAL.
        for suffix in ("-wal", "-shm"):
            (self.root / "data" / ("roleweaver.sqlite3" + suffix)).unlink(
                missing_ok=True
            )
        (self.root / "data/roleweaver.sqlite3").write_bytes(b"corrupt")
        self.start()
        self.assertFalse(self.request("/api/databases")["available"])
        self.assertIn(b"recovery-root", self.request("/"))
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/state")
        self.assertEqual(cm.exception.code, 503)
        preview = self.action("preview", dict(name=point["name"], scope="all"))
        self.action("restore", dict(token=preview["token"], game_stopped=True))
        self.assertTrue(self.request("/api/databases")["available"])

    def test_cross_origin_and_invalid_archive_rejected(self):
        self.start()
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/databases/create", {}, origin="https://outside.invalid")
        self.assertEqual(cm.exception.code, 403)
        with self.assertRaises(HTTPError) as cm:
            self.request("/api/databases/download?name=../config.json")
        self.assertEqual(cm.exception.code, 400)
        self.request(
            "/api/databases/import", b"not a zip", content_type="application/zip"
        )
        for _ in range(100):
            job = self.request("/api/databases")["job"]
            if not job["running"]:
                break
            time.sleep(0.02)
        self.assertTrue(job["error"])
        self.assertTrue(self.request("/api/databases")["available"])

    def test_invalid_framing_and_cross_site_requests_leave_dashboard_usable(self):
        self.start()
        for path in ("/api/llm-test", "/api/databases/create"):
            for extra, body, expected in (
                ([("Content-Length", "2")], b"{}", 400),
                ([("Transfer-Encoding", "chunked")], b"{}", 400),
                ([("Sec-Fetch-Site", "cross-site")], b"{}", 403),
                (
                    [
                        ("Origin", "http://127.0.0.1:" + str(self.port)),
                        ("Origin", "http://127.0.0.1:" + str(self.port)),
                    ],
                    b"{}",
                    403,
                ),
                ([], b"[]", 400),
            ):
                with self.subTest(path=path, extra=extra, body=body):
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", self.port, timeout=5
                    )
                    try:
                        connection.putrequest("POST", path)
                        connection.putheader("Content-Type", "application/json")
                        connection.putheader("Cookie", self.cookie)
                        connection.putheader("Content-Length", str(len(body)))
                        for name, value in extra:
                            connection.putheader(name, value)
                        connection.endheaders(body)
                        response = connection.getresponse()
                        self.assertEqual(response.status, expected, response.read())
                    finally:
                        connection.close()
        self.assertTrue(self.request("/api/databases")["available"])
        self.assertIn("npcs", self.request("/api/state"))


if __name__ == "__main__":
    unittest.main()
