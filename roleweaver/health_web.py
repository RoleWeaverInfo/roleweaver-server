"""Health and support routes also work while application databases are offline."""

from pathlib import Path
from urllib.parse import urlparse


def handle(handler, runtime, method):
    path = urlparse(handler.path).path
    if path not in ("/health", "/health.js", "/api/health", "/api/support-report"):
        return False
    if method != "GET":
        handler.respond(405, {"error": "Use GET for health and support reports"})
    elif path == "/api/health":
        handler.respond(200, runtime.monitor.snapshot())
    elif path == "/api/support-report":
        handler.respond(
            200,
            runtime.monitor.report(),
            "application/zip",
            download="roleweaver-support.zip",
        )
    else:
        name = "health.js" if path.endswith(".js") else "health.html"
        handler.respond(
            200,
            (Path(__file__).parent / "static" / name).read_bytes(),
            ("application/javascript" if name.endswith(".js") else "text/html")
            + "; charset=utf-8",
        )
    return True
