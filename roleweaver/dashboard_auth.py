"""Shared administrator login and server-side password reset, independent of SQLite."""

import argparse
from collections import deque
import getpass
import hashlib
import hmac
from http.cookies import SimpleCookie, CookieError
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time

ITERATIONS = 600_000
SESSION_SECONDS = 12 * 60 * 60
PROBE_PATHS = frozenset(
    (
        "/api/health",
        "/api/companions",
        "/api/state",
        "/api/conversation-settings",
        "/api/actions",
    )
)


def credential_path(config_path):
    return Path(config_path).parent / "dashboard-auth.json"


def read_record(path):
    """Fail closed on damaged credentials; never include their contents in errors."""
    try:
        if path.is_symlink() or path.stat().st_size > 4096:
            raise ValueError
        record = json.loads(path.read_text(encoding="utf-8"))
        if (
            record["version"] != 1
            or record["iterations"] != ITERATIONS
            or not re.fullmatch(r"[a-f0-9]{32}", record["salt"])
            or not re.fullmatch(r"[a-f0-9]{64}", record["digest"])
            or not re.fullmatch(r"[a-f0-9]{64}", record["probe_token"])
        ):
            raise ValueError
        return record
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError(
            "Dashboard credentials unavailable; reset the password on the server"
        ) from None


def set_password(config_path, password, *, initial=False):
    """Atomic, private credential replacement. Reset also revokes local probe access."""
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        raise ValueError("Use a password between 8 and 256 characters")
    path = credential_path(config_path)
    salt = secrets.token_bytes(16)
    record = dict(
        version=1,
        iterations=ITERATIONS,
        salt=salt.hex(),
        digest=hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex(),
        probe_token=secrets.token_hex(32),
    )
    fd, name = tempfile.mkstemp(prefix=".dashboard-auth-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(record, out)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        if initial:
            try:
                os.link(name, path)  # Never overwrite a concurrent password reset.
            except FileExistsError:
                pass
        else:
            os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def probe_headers(config_path):
    """Read-only server tooling credential. Not sent to browsers or remote URLs."""
    path = credential_path(config_path)
    if not path.exists():
        return {}  # Compatibility with software releases predating dashboard login.
    return {"X-RoleWeaver-Probe": read_record(path)["probe_token"]}


class LoginBusy(ValueError):
    pass


class DashboardAuth:
    def __init__(self, config_path, port, clock=time.monotonic):
        self.path = credential_path(config_path)
        if not self.path.exists():
            set_password(config_path, "roleweaver", initial=True)
        self.record = read_record(self.path)
        self.cookie = "rw_session_" + str(port)
        self.clock = clock
        self.lock = threading.RLock()
        self.sessions = {}
        self.attempts = deque()
        self.verifying = threading.BoundedSemaphore(1)

    def refresh(self):
        record = read_record(self.path)
        if record != self.record:
            self.sessions.clear()
            self.record = record
        now = self.clock()
        self.sessions = {
            key: expiry for key, expiry in self.sessions.items() if expiry > now
        }

    def login(self, password):
        if not isinstance(password, str) or not 1 <= len(password) <= 256:
            return None
        if not self.verifying.acquire(blocking=False):
            raise LoginBusy("A login is being checked; try again shortly")
        try:
            with self.lock:
                self.refresh()
                now = self.clock()
                while self.attempts and self.attempts[0] <= now - 60:
                    self.attempts.popleft()
                if len(self.attempts) >= 10:
                    raise LoginBusy(
                        "Too many login attempts; wait one minute and try again"
                    )
                self.attempts.append(now)
                record = dict(self.record)
            digest = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(record["salt"]), ITERATIONS
            ).hex()
            with self.lock:
                self.refresh()
                if record != self.record or not hmac.compare_digest(
                    digest, record["digest"]
                ):
                    return None
                if len(self.sessions) >= 32:
                    self.sessions.pop(next(iter(self.sessions)))
                token = secrets.token_urlsafe(32)
                self.sessions[token] = self.clock() + SESSION_SECONDS
                return token
        finally:
            self.verifying.release()

    def token(self, headers):
        values = headers.get_all("Cookie", [])
        if len(values) != 1 or len(values[0]) > 4096:
            return ""
        try:
            cookie = SimpleCookie()
            cookie.load(values[0])
            token = cookie[self.cookie].value
            return token if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else ""
        except (CookieError, KeyError):
            return ""

    def authenticated(self, headers):
        with self.lock:
            self.refresh()
            return self.token(headers) in self.sessions

    def probe(self, headers, method, path):
        if method != "GET" or path not in PROBE_PATHS:
            return False
        values = headers.get_all("X-RoleWeaver-Probe", [])
        if len(values) != 1 or not re.fullmatch(r"[a-f0-9]{64}", values[0]):
            return False
        with self.lock:
            self.refresh()
            return hmac.compare_digest(values[0], self.record["probe_token"])

    def logout(self, headers):
        with self.lock:
            self.sessions.pop(self.token(headers), None)

    def cookie_header(self, token=""):
        # HTTP is restricted to loopback/SSH. Secure would prevent cookies over HTTP
        # on some browsers; a public TLS/reverse-proxy deployment is not supported.
        return f"{self.cookie}={token}; Path=/; HttpOnly; SameSite=Strict" + (
            "" if token else "; Max-Age=0"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Set the dashboard password on the server"
    )
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    if not args.config.is_file():
        parser.error("Choose the installed world's existing config.json")
    try:
        password = getpass.getpass("New dashboard password: ")
        if password != getpass.getpass("Repeat dashboard password: "):
            raise ValueError("Passwords did not match")
        set_password(args.config, password)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(
        "Dashboard password changed. Existing logins are revoked; no restart is needed."
    )


if __name__ == "__main__":
    main()
