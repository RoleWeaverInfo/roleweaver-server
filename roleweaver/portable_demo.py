"""Small, authenticated controls for the packaged Windows demo only.

The normal add-on does not expose a DM-password editor. A trusted systemd
environment value must name this demo's settings file to enable these routes.
Passwords never enter logs, the translation cache or world backups.
"""

import json
import os
from pathlib import Path
import tempfile

from .auth_web import request_body
from .dashboard_auth import LoginBusy, set_password


def settings_path(config_path):
    supplied = os.environ.get("ROLEWEAVER_PORTABLE_SETTINGS", "")
    if not supplied:
        return None
    path = Path(supplied)
    expected = Path(config_path).resolve().parent / "settings.json"
    if path.is_symlink() or path.resolve() != expected or not path.is_file():
        return None
    value = json.loads(path.read_text())
    if value.get("id") != "qemu_demo":
        return None
    return path


def write_settings(path, value):
    fd, name = tempfile.mkstemp(prefix=".demo-settings-", dir=path.parent)
    try:
        os.chmod(name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def change_password(auth, config_path, path, body):
    if not isinstance(body, dict) or set(body) != {
        "current_password",
        "kind",
        "password",
    }:
        raise ValueError("Supply the current dashboard password and one new password")
    kind, password = body["kind"], body["password"]
    if kind not in ("dashboard", "dm"):
        raise ValueError("Choose Dashboard or DM password")
    maximum = 256 if kind == "dashboard" else 32
    if not isinstance(password, str) or not 8 <= len(password) <= maximum:
        raise ValueError(f"Use a password between 8 and {maximum} characters")
    if kind == "dm" and any(ord(char) < 33 or ord(char) > 126 for char in password):
        raise ValueError(
            "Use printable ASCII characters without spaces for the DM password"
        )
    with auth.lock:
        token = auth.login(body["current_password"])
        if token is None:
            raise PermissionError("Incorrect current dashboard password")
        if kind == "dashboard":
            set_password(config_path, password)
            # Refresh revokes old sessions; issue a replacement for this launcher.
            token = auth.login(password)
        else:
            value = json.loads(path.read_text())
            value["dm_password"] = password
            write_settings(path, value)
    return dict(ok=True, restart_required=kind == "dm"), token


def handle(handler, auth, config_path, method):
    if handler.path != "/api/demo-password":
        return False
    path = settings_path(config_path)
    if path is None:
        handler.respond(
            404, {"error": "Password controls require the updated portable demo"}
        )
        return True
    if method == "GET":
        handler.respond(200, {"available": True, "dm_requires_restart": True})
        return True
    if method != "POST":
        handler.respond(405, {"error": "Use GET or POST"})
        return True
    try:
        result, token = change_password(auth, config_path, path, request_body(handler))
        handler.respond(200, result, headers={"Set-Cookie": auth.cookie_header(token)})
    except LoginBusy as exc:
        handler.respond(429, {"error": str(exc)})
    except PermissionError:
        handler.respond(401, {"error": "Incorrect current dashboard password"})
    except (ValueError, TypeError, KeyError):
        handler.respond(
            400,
            {
                "error": "Check the password fields. Dashboard: 8–256 characters. DM: 8–32 ASCII characters, no spaces."
            },
        )
    except OSError:
        handler.respond(
            503,
            {"error": "Password could not be saved; check permissions inside the demo"},
        )
    return True
