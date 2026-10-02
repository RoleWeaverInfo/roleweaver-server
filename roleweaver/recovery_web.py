"""Small recovery HTTP surface that never depends on a working world database."""

import json
from pathlib import Path
import shutil
import tempfile
from urllib.parse import parse_qs, urlparse

from .db_recovery import MAX_UPLOAD
from . import http_security


def handle(handler, runtime, method):
    parsed = urlparse(handler.path)
    path = parsed.path
    if method == "GET" and (
        path in ("/recovery", "/database-recovery.js")
        or path == "/"
        and (runtime.app is None or runtime.maintenance)
    ):
        name = "database-recovery.js" if path.endswith(".js") else "recovery.html"
        content_type = "application/javascript" if path.endswith(".js") else "text/html"
        handler.respond(
            200,
            (Path(__file__).parent / "static" / name).read_bytes(),
            content_type + "; charset=utf-8",
        )
        return True
    if not path.startswith("/api/databases"):
        return False
    try:
        if method == "GET":
            if path == "/api/databases":
                handler.respond(200, runtime.status())
            elif path == "/api/databases/download":
                name = parse_qs(parsed.query).get("name", [""])[0]
                with runtime.manager.path(name).open("rb") as stream:
                    handler.send_response(200)
                    handler.send_header("Content-Type", "application/zip")
                    handler.send_header(
                        "Content-Disposition", f'attachment; filename="{name}"'
                    )
                    handler.send_header(
                        "Content-Length", str(runtime.manager.path(name).stat().st_size)
                    )
                    handler.send_header("Cache-Control", "no-store")
                    handler.send_header("X-Content-Type-Options", "nosniff")
                    handler.end_headers()
                    shutil.copyfileobj(stream, handler.wfile)
            else:
                handler.respond(404, {"error": "Unknown recovery operation"})
            return True
        length = http_security.body_length(
            handler.headers, MAX_UPLOAD if path.endswith("/import") else 65536
        )
        if path == "/api/databases/import":
            if handler.headers.get("Content-Type") != "application/zip":
                raise ValueError("Choose a Role Weaver database recovery ZIP")
            with http_security.recovery_upload(handler):
                runtime.manager.space(length * 2)
                upload = tempfile.NamedTemporaryFile(
                    prefix=".upload-", dir=runtime.directory, delete=False
                )
                source = Path(upload.name)
                try:
                    with upload:
                        for chunk in http_security.body_chunks(
                            handler, length, seconds=300
                        ):
                            upload.write(chunk)

                    def import_file():
                        try:
                            return runtime.manager.import_archive(source)
                        finally:
                            source.unlink(missing_ok=True)

                    result = runtime.submit(
                        "Import and verify recovery point", import_file
                    )
                except BaseException:
                    upload.close()
                    source.unlink(missing_ok=True)
                    raise
        else:
            if handler.headers.get("Content-Type") != "application/json":
                raise ValueError("Same-origin JSON required")
            body = json.loads(b"".join(http_security.body_chunks(handler, length)))
            if not isinstance(body, dict):
                raise ValueError("Invalid recovery request")
            manager = runtime.manager
            actions = {
                "/api/databases/check": ("Check databases", runtime.check),
                "/api/databases/create": ("Create recovery point", runtime.capture),
                "/api/databases/verify": (
                    "Verify recovery point",
                    lambda: manager.verify(body["name"]),
                ),
                "/api/databases/preview": (
                    "Preview restore",
                    lambda: runtime.preview(body["name"], body["scope"]),
                ),
                "/api/databases/restore": (
                    "Restore databases",
                    lambda: runtime.restore(body["token"], body.get("game_stopped")),
                ),
                "/api/databases/settings": (
                    "Save backup settings",
                    lambda: manager.configure(body),
                ),
                "/api/databases/protect": (
                    "Change protection",
                    lambda: manager.protect(body["name"], body["protected"]),
                ),
                "/api/databases/delete": (
                    "Delete recovery point",
                    lambda: manager.delete(body["name"]),
                ),
                "/api/databases/retry": ("Retry companion startup", runtime.retry),
            }
            if path not in actions:
                raise ValueError("Unknown recovery operation")
            result = runtime.submit(*actions[path])
        handler.respond(202, result)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        handler.respond(400, {"error": runtime.failure(exc)})
    return True
