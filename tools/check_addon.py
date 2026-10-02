"""Read-only companion/bridge readiness check. Never triggers an LLM request."""

import argparse
import json
import urllib.request
import urllib.error
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roleweaver.dashboard_auth import probe_headers


def check(port, config=None):
    if not 1024 <= port <= 65535:
        raise ValueError("Dashboard port must be 1024–65535")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    headers = probe_headers(config) if config else {}

    def get(path):
        with opener.open(
            urllib.request.Request(
                "http://127.0.0.1:" + str(port) + path, headers=headers
            ),
            timeout=5,
        ) as response:
            return json.load(response)

    state = get("/api/state")
    conversation = get("/api/conversation-settings")
    actions = get("/api/actions")
    rows = [
        ("Dashboard", True),
        ("Redis", bool(state.get("redis"))),
        ("Game conversation bridge", conversation.get("status") == "applied"),
        ("Action bridge protocol", bool(actions.get("ready"))),
    ]
    for name, ok in rows:
        print(("OK   " if ok else "WAIT ") + name)
    print("Connected NPCs:", len(state.get("states", {})))
    print("AI provider:", state.get("llm_service", state.get("provider", "unknown")))
    print("No provider request was made. Use the dashboard connection test separately.")
    return all(ok for _, ok in rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8743)
    p.add_argument(
        "--config",
        type=Path,
        help="Installed world's config.json for authenticated local checks",
    )
    args = p.parse_args()
    try:
        raise SystemExit(0 if check(args.port, args.config) else 1)
    except (ValueError, OSError, urllib.error.URLError) as e:
        print(
            "Cannot complete check:",
            type(e).__name__,
            "— confirm the service port and pass --config /path/to/installed/config.json for dashboard login.",
        )
        raise SystemExit(1)
