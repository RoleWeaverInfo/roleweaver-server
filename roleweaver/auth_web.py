"""Authentication gate before any dashboard, health or database recovery route."""

import json
from pathlib import Path
from urllib.parse import urlparse

from . import http_security
from .dashboard_auth import LoginBusy


def request_body(handler):
    if handler.headers.get("Content-Type") != "application/json":
        raise ValueError("Send a JSON request")
    length = http_security.body_length(handler.headers, 4096)
    body = json.loads(b"".join(http_security.body_chunks(handler, length)))
    if not isinstance(body, dict):
        raise ValueError("Invalid authentication request")
    return body


def handle(handler, auth, method):
    path = urlparse(handler.path).path
    if method == "GET" and path in ("/login", "/login.js", "/login-image.png"):
        name, kind = {
            "/login": ("login.html", "text/html; charset=utf-8"),
            "/login.js": ("login.js", "application/javascript; charset=utf-8"),
            "/login-image.png": ("rw_server_splash.png", "image/png"),
        }[path]
        handler.respond(
            200, (Path(__file__).parent / "static" / name).read_bytes(), kind
        )
        return True
    if path == "/api/login" and method == "POST":
        try:
            body = request_body(handler)
            if set(body) != {"password"}:
                raise ValueError("Invalid login request")
            token = auth.login(body["password"])
            if not token:
                handler.respond(401, {"error": "Incorrect dashboard password"})
            else:
                handler.respond(
                    200, {"ok": True}, headers={"Set-Cookie": auth.cookie_header(token)}
                )
        except LoginBusy as exc:
            handler.respond(429, {"error": str(exc)}, headers={"Retry-After": "60"})
        except (ValueError, OSError):
            handler.respond(
                400,
                {
                    "error": "Unable to sign in. Check the request or reset the password on the server."
                },
            )
        return True
    if not auth.authenticated(handler.headers):
        if auth.probe(handler.headers, method, path):
            return False
        if method == "GET" and not path.startswith("/api/"):
            handler.respond(303, b"", headers={"Location": "/login"})
        else:
            handler.respond(
                401, {"error": "Sign in to the dashboard", "login": "/login"}
            )
        return True
    if path == "/api/logout" and method == "POST":
        # Origin/Host checks already ran. JSON is also required to reject form posts.
        try:
            if request_body(handler):
                raise ValueError("Invalid logout request")
        except (ValueError, OSError):
            handler.respond(400, {"error": "Send a JSON logout request"})
        else:
            auth.logout(handler.headers)
            handler.respond(
                200, {"ok": True}, headers={"Set-Cookie": auth.cookie_header()}
            )
        return True
    if path == "/api/session" and method == "GET":
        handler.respond(200, {"authenticated": True})
        return True
    if path == "/session.js" and method == "GET":
        handler.respond(
            200,
            (Path(__file__).parent / "static/session.js").read_bytes(),
            "application/javascript; charset=utf-8",
        )
        return True
    return False
