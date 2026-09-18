"""Loopback dashboard HTTP routes and application lifecycle."""

from .authoring import catalog
import argparse
import json
import os
import secrets
import time
from . import backup
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .service import Service
from . import __version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    os.umask(0o077)
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text())
    app = Service(config_path.parent / "data", config)
    port = int(config.get("web_port", 8741))
    page = (Path(__file__).parent / "static/index.html").read_bytes()

    previews = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, data, content_type="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            host = self.headers.get("Host", "")
            if host not in (f"localhost:{port}", f"127.0.0.1:{port}"):
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin == "http://" + host

        def do_GET(self):
            if not self.allowed():
                return self.respond(403, {"error": "Use the local dashboard address"})
            parsed = urlparse(self.path)
            if parsed.path == "/":
                return self.respond(200, page, "text/html; charset=utf-8")
            if parsed.path == "/authoring.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/authoring.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path == "/drafts.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/drafts.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path == "/safeguards.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/safeguards.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path == "/insights.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/insights.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path in ("/api/knowledge", "/api/usage"):
                try:
                    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                    data = (
                        app.knowledge(q.get("npc", ""), q.get("player", ""))
                        if parsed.path.endswith("knowledge")
                        else app.usage.report(
                            q.get("window", "24h"),
                            q.get("npc", ""),
                            q.get("phase", ""),
                            q.get("model", ""),
                        )
                    )
                    return self.respond(200, data)
                except (ValueError, TypeError) as exc:
                    return self.respond(400, {"error": str(exc)})
            if parsed.path == "/merchants.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/merchants.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path == "/api/merchants":
                return self.respond(200, app.merchant_status())
            if parsed.path == "/actions.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/actions.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path == "/api/actions":
                return self.respond(200, app.action_status())
            if parsed.path == "/conversation.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/conversation.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path == "/api/llm":
                return self.respond(200, app.llm_status())
            if parsed.path == "/llm.js":
                return self.respond(
                    200,
                    (Path(__file__).parent / "static/llm.js").read_bytes(),
                    "application/javascript; charset=utf-8",
                )
            if parsed.path == "/api/conversation-settings":
                return self.respond(200, app.conversation_status())
            if parsed.path == "/api/catalog":
                return self.respond(200, catalog())
            if parsed.path == "/api/access-lore":
                return self.respond(200, app.store.access_lore())
            if parsed.path == "/api/world-documents":
                return self.respond(
                    200,
                    {
                        "documents": app.store.world_documents(),
                        "active_characters": len(app.store.world_lore()),
                        "limit": 20000,
                    },
                )
            if parsed.path == "/api/recovery":
                return self.respond(200, app.recovery.status())
            if parsed.path == "/api/recovery-download":
                try:
                    return self.respond(
                        200,
                        app.recovery.read(parse_qs(parsed.query).get("name", [""])[0]),
                    )
                except (ValueError, OSError) as exc:
                    return self.respond(400, {"error": str(exc)})
            if parsed.path == "/api/backup":
                return self.respond(200, app.backup_data())
            if parsed.path == "/api/lore":
                return self.respond(200, {"text": app.store.world_lore()})
            if parsed.path == "/api/state":
                return self.respond(200, app.snapshot())
            if parsed.path == "/api/safeguards":
                return self.respond(200, app.safeguard_status())
            if parsed.path == "/api/detail":
                npc = parse_qs(parsed.query).get("npc", [""])[0]
                return self.respond(
                    200,
                    {
                        "messages": app.store.transcript(npc),
                        "memories": app.store.memories(npc),
                    },
                )
            self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if (
                not self.allowed()
                or self.headers.get("Content-Type") != "application/json"
            ):
                return self.respond(403, {"error": "Same-origin JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (
                    not 0
                    < length
                    <= (
                        backup.LIMIT
                        if self.path == "/api/restore-preview"
                        else 256000 if self.path == "/api/world-document" else 65536
                    )
                ):
                    raise ValueError("Invalid request length")
                body = json.loads(self.rfile.read(length))
                if self.path in ("/api/llm-test", "/api/llm-models"):
                    return self.respond(
                        200, app.probe_llm(body, self.path.endswith("models"))
                    )
                if self.path == "/api/llm":
                    return self.respond(200, app.save_llm(body))
                if self.path == "/api/restore-preview":
                    data = backup.validate(body)
                    token = secrets.token_hex(24)
                    with app.lock:
                        previews.clear()
                        previews[token] = (time.monotonic(), data)
                    return self.respond(
                        200,
                        {
                            "token": token,
                            "npcs": [p["name"] for p in data["npcs"]],
                            "messages": len(data["messages"]),
                            "memories": len(data["memories"]),
                            "lore_characters": len(data["world_lore"]),
                            "placements": len(data["placements"]),
                            "access_lore": len(data["access_lore"]),
                            "safeguards": "safeguards" in data,
                            "world_documents": len(data["world_documents"]),
                        },
                    )
                if self.path == "/api/restore":
                    with app.lock:
                        entry = previews.pop(body.get("token"), None)
                    if not entry or time.monotonic() - entry[0] > 600:
                        raise ValueError(
                            "Restore preview expired. Preview the backup again."
                        )
                    return self.respond(200, app.restore_data(entry[1]))
                with app.lock:
                    if app.restoring:
                        raise ValueError("Restore in progress; wait before editing")
                    if self.path == "/api/lore":
                        result = {"text": app.save_world_lore(body["text"])}
                    elif self.path == "/api/usage-pricing":
                        result = app.usage.save_price(body["model"], body["rates"])
                    elif self.path == "/api/memory-edit":
                        result = app.edit_memory(body["npc"], body["id"], body["text"])
                    elif self.path == "/api/merchant-rules":
                        result = app.save_merchant_rules(
                            body["npc"], body["rules"], body["revision"]
                        )
                    elif self.path == "/api/merchant-stock":
                        result = app.edit_merchant_stock(
                            body["npc"],
                            body["operation"],
                            body["revision"],
                            body["item"],
                            body["quantity"],
                        )
                    elif self.path == "/api/merchant-example":
                        result = app.merchant_example()
                    elif self.path == "/api/action-policy":
                        result = app.save_action_policy(body["npc"], body["policy"])
                    elif self.path == "/api/action-capture":
                        result = app.capture_destination(
                            body["id"], body["name"], body["dm"]
                        )
                    elif self.path == "/api/action-delete-destination":
                        result = app.delete_destination(body["id"])
                    elif self.path == "/api/action-run":
                        result = app.run_action(body["npc"], body["choice"])
                    elif self.path == "/api/action-stop":
                        result = app.stop_action(body["npc"])
                    elif self.path == "/api/conversation-settings":
                        result = app.save_conversation(body)
                    elif self.path == "/api/conversation-reset":
                        result = app.save_conversation(
                            app.conversation_policy, reset=True
                        )
                    elif self.path == "/api/safeguards":
                        result = app.save_safeguards(body)
                    elif self.path in (
                        "/api/world-document",
                        "/api/world-document-toggle",
                        "/api/world-document-delete",
                    ):
                        if self.path.endswith("-toggle"):
                            result = app.store.toggle_world_document(
                                body["id"], body["active"]
                            )
                        elif self.path.endswith("-delete"):
                            app.store.delete_world_document(body["id"])
                            result = {"ok": True}
                        else:
                            result = app.store.save_world_document(body)
                        for npc in app.busy:
                            app.generations[npc] = app.generations.get(npc, 0) + 1
                    elif self.path in (
                        "/api/access-lore",
                        "/api/access-lore-delete",
                        "/api/access-lore-toggle",
                    ):
                        if self.path.endswith("-delete"):
                            app.store.delete_access_lore(body["id"])
                            result = {"ok": True}
                        elif self.path.endswith("-toggle"):
                            result = app.store.toggle_access_lore(
                                body["id"], body["active"]
                            )
                        else:
                            result = app.store.save_access_lore(body)
                        for npc in app.busy:
                            app.generations[npc] = app.generations.get(npc, 0) + 1
                    elif self.path == "/api/duplicate":
                        result = app.duplicate_profile(
                            body["source"], body["id"], body["name"]
                        )
                    elif self.path == "/api/profile":
                        result = app.save_profile(body)
                    elif self.path == "/api/delete":
                        result = app.delete_npc(body["npc"])
                    elif self.path == "/api/manage":
                        result = {
                            "request": app.manage_npc(
                                body["npc"],
                                body["action"],
                                body.get("dm"),
                                body.get("persistence"),
                                body.get("return_mode"),
                            )
                        }
                    elif self.path == "/api/spawn":
                        result = {
                            "request": app.spawn_at_dm(
                                body["npc"],
                                body["dm"],
                                body["blueprint"],
                                body.get("persistence", "temporary"),
                            )
                        }
                    elif self.path == "/api/startup-auto":
                        result = app.set_startup_auto(body["enabled"])
                    elif self.path == "/api/control-all":
                        result = app.control_all(body["mode"])
                    elif self.path == "/api/control":
                        result = {"request": app.control(body["npc"], body["mode"])}
                    elif self.path == "/api/memory":
                        app.store.add_memory(
                            body["npc"], body.get("player", ""), body["text"]
                        )
                        app.generations[body["npc"]] = (
                            app.generations.get(body["npc"], 0) + 1
                        )
                        result = {"ok": True}
                    elif self.path == "/api/forget":
                        app.store.forget(body["npc"], body["id"])
                        app.generations[body["npc"]] = (
                            app.generations.get(body["npc"], 0) + 1
                        )
                        result = {"ok": True}
                    else:
                        return self.respond(404, {"error": "Not found"})
                self.respond(200, result)
            except (ValueError, KeyError, TypeError) as exc:
                self.respond(400, {"error": str(exc)})
            except Exception:
                self.respond(
                    503,
                    {
                        "error": "Service unavailable; check the game and Redis connection"
                    },
                )

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    app.start()
    print(
        f"Role Weaver Server {__version__} â€” http://127.0.0.1:{port} â€” provider: {config['provider']}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.running = False
        app.recovery.stop.set()
        if app.recovery.thread:
            app.recovery.thread.join(timeout=5)
        app.pool.shutdown(wait=True, cancel_futures=True)
        server.server_close()


if __name__ == "__main__":
    main()
