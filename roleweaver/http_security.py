"""Bounds for the trusted-local dashboard; not a public authentication service."""

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import threading
import time


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, handler, max_connections=16):
        self.connections = threading.BoundedSemaphore(max_connections)
        self.recovery_upload = threading.BoundedSemaphore(1)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            # Do not block the accept loop trying to write to an unread socket.
            self.shutdown_request(request)
            return
        request.settimeout(10)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()


def allowed(headers, port):
    hosts = headers.get_all("Host", [])
    origins = headers.get_all("Origin", [])
    sites = headers.get_all("Sec-Fetch-Site", [])
    return (
        len(hosts) == 1
        and hosts[0] in (f"localhost:{port}", f"127.0.0.1:{port}")
        and len(origins) <= 1
        and (not origins or origins[0] == "http://" + hosts[0])
        and len(sites) <= 1
        and (not sites or sites[0] in ("same-origin", "none"))
    )


def body_length(headers, maximum):
    lengths = headers.get_all("Content-Length", [])
    if (
        headers.get_all("Transfer-Encoding")
        or len(lengths) != 1
        or not lengths[0].isascii()
        or not lengths[0].isdigit()
        or len(lengths[0]) > 10
    ):
        raise ValueError(
            "Supply one valid Content-Length; chunked requests are unsupported"
        )
    length = int(lengths[0])
    if not 0 < length <= maximum:
        raise ValueError("Invalid request length")
    return length


def body_chunks(handler, length, seconds=20):
    """Bound total upload time, including clients that send occasional bytes."""
    deadline = time.monotonic() + seconds
    remaining = length
    while remaining:
        left = deadline - time.monotonic()
        if left <= 0:
            raise ValueError("Request upload timed out")
        handler.connection.settimeout(min(10, left))
        chunk = handler.rfile.read1(min(65536, remaining))
        if not chunk:
            raise ValueError("Request upload was incomplete")
        remaining -= len(chunk)
        yield chunk


@contextmanager
def recovery_upload(handler):
    slot = handler.server.recovery_upload
    if not slot.acquire(blocking=False):
        raise ValueError(
            "Another recovery upload is in progress; wait for it to finish"
        )
    try:
        yield
    finally:
        slot.release()
