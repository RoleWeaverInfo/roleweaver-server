"""Read-only companion/bridge readiness check. Never triggers an LLM request."""

import argparse
import json
import urllib.request
import urllib.error


def check(port):
    if not 1024 <= port <= 65535:
        raise ValueError("Dashboard port must be 1024–65535")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(path):
        with opener.open("http://127.0.0.1:" + str(port) + path, timeout=5) as response:
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
    args = p.parse_args()
    try:
        raise SystemExit(0 if check(args.port) else 1)
    except (ValueError, OSError, urllib.error.URLError) as e:
        print(
            "Cannot complete check:",
            type(e).__name__,
            "— confirm the companion is running on the selected port.",
        )
        raise SystemExit(1)
