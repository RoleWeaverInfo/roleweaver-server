"""Malformed/local-browser traffic must not monopolize dashboard resources."""

from email.message import Message
from http.server import BaseHTTPRequestHandler
import io
import socket
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from roleweaver.http_security import (
    DashboardServer,
    allowed,
    body_length,
    body_chunks,
    recovery_upload,
)


class HTTPBoundsTests(unittest.TestCase):
    def headers(self, *pairs):
        headers = Message()
        for key, value in pairs:
            headers[key] = value
        return headers

    def test_browser_origin_host_and_fetch_metadata(self):
        base = (("Host", "127.0.0.1:8743"),)
        self.assertTrue(allowed(self.headers(*base), 8743))
        self.assertTrue(
            allowed(
                self.headers(
                    *base,
                    ("Origin", "http://127.0.0.1:8743"),
                    ("Sec-Fetch-Site", "same-origin"),
                ),
                8743,
            )
        )
        for extra in (
            ("Origin", "null"),
            ("Origin", "https://outside.invalid"),
            ("Host", "127.0.0.1:8743"),
            ("Sec-Fetch-Site", "cross-site"),
            ("Sec-Fetch-Site", "same-site"),
        ):
            self.assertFalse(allowed(self.headers(*base, extra), 8743))
        self.assertFalse(allowed(self.headers(("Host", "outside.invalid:8743")), 8743))

    def test_body_size_and_ambiguous_framing(self):
        self.assertEqual(body_length(self.headers(("Content-Length", "2")), 10), 2)
        for values in (
            (),
            (("Content-Length", "-1"),),
            (("Content-Length", "11"),),
            (("Content-Length", "2"), ("Content-Length", "2")),
            (("Content-Length", "2"), ("Transfer-Encoding", "chunked")),
            (("Content-Length", "２"),),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                body_length(self.headers(*values), 10)

    def test_incomplete_or_slow_upload_is_bounded(self):
        handler = SimpleNamespace(connection=Mock(), rfile=io.BytesIO(b"x"))
        with self.assertRaises(ValueError):
            list(body_chunks(handler, 2))
        handler.rfile = io.BytesIO(b"x" * 65537)
        with (
            patch("roleweaver.http_security.time.monotonic", side_effect=[0, 0, 21]),
            self.assertRaises(ValueError),
        ):
            list(body_chunks(handler, 65537))

    def test_recovery_upload_is_exclusive_and_released_on_failure(self):
        handler = SimpleNamespace(
            server=SimpleNamespace(recovery_upload=threading.BoundedSemaphore(1))
        )
        with self.assertRaises(RuntimeError), recovery_upload(handler):
            with self.assertRaises(ValueError), recovery_upload(handler):
                self.fail("second upload admitted")
            raise RuntimeError("fixture upload failure")
        with recovery_upload(handler):
            pass

    def test_socket_threads_are_bounded_and_recover(self):
        release = threading.Event()
        admitted = threading.Semaphore(0)

        class Handler(BaseHTTPRequestHandler):
            def handle(self):
                admitted.release()
                release.wait(5)

            def log_message(self, *_):
                pass

        server = DashboardServer(("127.0.0.1", 0), Handler, max_connections=2)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        clients = []
        try:
            for _ in range(2):
                clients.append(
                    socket.create_connection(server.server_address, timeout=2)
                )
                self.assertTrue(admitted.acquire(timeout=2))
            with socket.create_connection(server.server_address, timeout=2) as third:
                self.assertEqual(third.recv(1), b"")
            release.set()
            for client in clients:
                self.assertEqual(client.recv(1), b"")
        finally:
            release.set()
            for client in clients:
                client.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
