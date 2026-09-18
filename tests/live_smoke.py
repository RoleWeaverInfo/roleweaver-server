"""Run only against the isolated rw_smoketest server / smoke Redis namespace."""

import json
import sys
import tempfile
import time
from pathlib import Path

from roleweaver.redis_wire import Redis
from roleweaver.service import Service


def main():
    redis = Redis()
    prefix = "roleweaver:smoke"
    states = {}
    acks = {}

    def consume(app=None):
        for _ in range(512):
            raw = redis.call("LPOP", prefix + ":events")
            if raw is None:
                break
            event = json.loads(raw)
            if event["kind"] == "state":
                states[event["npc"]] = event
            elif event["kind"] == "ack":
                acks[event["request"]] = event
            if app:
                app.event(event)

    def until(check, app=None):
        end = time.monotonic() + 8
        while time.monotonic() < end:
            consume(app)
            if check():
                return
            time.sleep(0.05)
        raise AssertionError("Timed out waiting for live bridge")

    until(lambda: "mira" in states)
    print("PASS native module loaded, NPC created and Redis state received")
    redis.call("DEL", prefix + ":commands")
    with tempfile.TemporaryDirectory() as directory:
        app = Service(Path(directory), {"provider": "offline", "redis_prefix": prefix})
        try:
            app.event(states["mira"])
            req = app.control("mira", "auto")
            until(lambda: req in acks, app)
            assert acks[req]["ok"] == 1 and states["mira"]["mode"] == "auto"
            print("PASS control command acknowledged by game")
            state = dict(states["mira"])
            event = dict(
                state,
                kind="chat",
                text="Test player: Hello Mira",
                player="test-key:Smoke Character",
                listener=state["object"],
                event_id=state["session"] + ":smoke",
            )
            app.event(event)
            until(
                lambda: any(
                    m["speaker"] == "npc" for m in app.store.transcript("mira")
                ),
                app,
            )
            print(
                "PASS offline response crossed service → Redis → game and acknowledged speech entered memory"
            )
            old_epoch = states["mira"]["epoch"]
            req = app.control("mira", "dm")
            until(lambda: req in acks, app)
            assert acks[req]["ok"] == 1 and states["mira"]["mode"] == "dm"
            current = states["mira"]
            redis.call(
                "RPUSH",
                prefix + ":commands",
                json.dumps(
                    dict(
                        kind="say",
                        npc="mira",
                        session=current["session"],
                        epoch=old_epoch,
                        expires=current["tick"] + 5,
                        request="stale-reply",
                        text="MUST NOT SPEAK",
                    )
                ),
            )
            until(lambda: "stale-reply" in acks, app)
            assert acks["stale-reply"]["ok"] == 0
            print("PASS game rejected stale speech after DM reservation")
            redis.call(
                "RPUSH",
                prefix + ":commands",
                json.dumps(
                    dict(
                        kind="say",
                        npc="mira",
                        session=current["session"],
                        epoch=current["epoch"],
                        expires=current["tick"] + 5,
                        request="dm-reply",
                        text="MUST NOT SPEAK",
                    )
                ),
            )
            until(lambda: "dm-reply" in acks, app)
            assert acks["dm-reply"]["ok"] == 0
            print("PASS game rejected current-epoch speech while DM reserved")
        finally:
            app.pool.shutdown(wait=True)
            app.store.db.close()


if __name__ == "__main__":
    main()
