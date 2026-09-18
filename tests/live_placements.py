"""Isolated native integration test; requires this VM's native server and compiler.

Uses a temporary module copy, Redis namespace, database and UDP port 5123.
Never reads or changes live Role Weaver profiles or memories.
"""

import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from roleweaver.service import Service
from roleweaver.store import DEFAULT_NPC


def main():
    world_managed = "--world-managed" in sys.argv
    base = Path(__file__).resolve().parent.parent
    native = base.parent / "RoleWeaver-Native-Server"
    sys.path.insert(0, str(base / "tools"))
    from module_copy import make_copy

    with tempfile.TemporaryDirectory(prefix="rw-placement-test-") as directory:
        root = Path(directory)
        userdata = root / "userdata"
        override = userdata / "override"
        override.mkdir(parents=True)
        module = userdata / "modules/rw_placement.mod"
        original = make_copy(
            native / "userdata/modules/DMFI MP Starter Mod.mod", module, "rw_testload"
        )
        prefix = "roleweaver:test:" + secrets.token_hex(8)
        for path in (base / "bridge").glob("*.nss"):
            if path.stem in (
                "rw_inc",
                "rw_init",
                "rw_chat",
                "rw_chat_inc",
                "rw_possess",
                "rw_tick",
                "rw_bind",
                "rw_unbind",
                "rw_creature",
                "rw_talk_inc",
                "rw_talk",
            ):
                (override / path.name).write_text(
                    path.read_text().replace("roleweaver:v1:", prefix + ":")
                )
        (override / "rw_settings.nss").write_text(
            'const string RW_WORLD="roleweaver_development";\n'
            + 'const string RW_REDIS_PREFIX="'
            + prefix
            + '";\n'
            + "const int RW_OWNS_PLACEMENTS="
            + str(int(not world_managed))
            + ";\nconst int RW_REGISTERS_CHAT="
            + str(int(not world_managed))
            + ";\n"
        )
        (override / "rw_testload.nss").write_text(
            """void main() {
            ExecuteScript("ORIGINAL", OBJECT_SELF);
            object a=GetObjectByTag("starting_area");
            object n=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",Location(a,Vector(20.0,14.0,0.0),0.0));
            SetTag(n,"rw_test_bound");
            ExecuteScript("rw_init",GetModule());
        }""".replace("ORIGINAL", original).replace(
                'ExecuteScript("rw_init",GetModule());',
                'ExecuteScript("rw_init",GetModule());'
                + (
                    'SetLocalString(n,"rw_profile","orren");ExecuteScript("rw_bind",n);'
                    if world_managed
                    else ""
                ),
            )
        )
        for name in (
            "rw_init",
            "rw_chat",
            "rw_possess",
            "rw_tick",
            "rw_bind",
            "rw_unbind",
            "rw_talk",
            "rw_testload",
        ):
            r = subprocess.run(
                [
                    str(base / "tools/nwnsc"),
                    "-n",
                    str(native / "runtime"),
                    "-i",
                    str(native / "nwscripts") + ";" + str(override),
                    str(override / (name + ".nss")),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode:
                raise RuntimeError(r.stdout + r.stderr)
        app = Service(
            root / "data",
            {
                "provider": "offline",
                "redis_prefix": prefix,
                "placement_owner": "world" if world_managed else "roleweaver",
            },
        )
        app.store.save(dict(DEFAULT_NPC, id="orren", name="Orren"))
        fixture = dict(
            world="roleweaver_development",
            session="previous",
            area="starting_area",
            area_tag="starting_area",
            resref="innkeeper",
            x=25.0,
            y=14.0,
            z=0.0,
            facing=90.0,
            dead=0,
        )
        app.store.save_placement(
            dict(fixture, npc="mira", name="Mira", tag="rw_test_spawn", source="spawn")
        )
        app.store.save_placement(
            dict(
                fixture,
                npc="orren",
                name="Orren",
                tag="rw_test_bound",
                source="bind",
                x=24.0,
            )
        )
        env = dict(os.environ)
        env.update(
            LD_PRELOAD=str(native / "plugins/NWNX_Core.so"),
            LD_LIBRARY_PATH=str(native / "plugins"),
            NWNX_CORE_LOAD_PATH=str(native / "plugins"),
            NWNX_CORE_SKIP_ALL="1",
            NWNX_CHAT_SKIP="n",
            NWNX_EVENTS_SKIP="n",
            NWNX_REDIS_SKIP="n",
            NWNX_REDIS_HOST="127.0.0.1",
            NWNX_REDIS_PORT="6379",
            NWNX_CORE_LOG_FILE_PATH=str(root / "nwnx.log"),
        )
        fifo = root / "console"
        os.mkfifo(fifo, 0o600)
        fd = os.open(fifo, os.O_RDWR)
        log = (root / "console.log").open("w")
        process = None

        def start():
            return subprocess.Popen(
                [
                    str(native / "runtime/bin/linux-x86/nwserver-linux"),
                    "-userdirectory",
                    str(userdata),
                    "-module",
                    "rw_placement",
                    "-port",
                    "5123",
                    "-publicserver",
                    "0",
                    "-playerpassword",
                    secrets.token_hex(16),
                    "-interactive",
                ],
                cwd=native / "runtime/bin/linux-x86",
                env=env,
                stdin=fd,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )

        def wait_for(check):
            end = time.monotonic() + 25
            while time.monotonic() < end:
                if process.poll() is not None:
                    raise AssertionError("Isolated test server exited")
                if check():
                    return
                time.sleep(0.2)
            raise AssertionError("Live placement test timed out: " + app.error)

        def placements():
            return {p["npc"]: p for p in app.store.placements()}

        def restored(previous):
            s = app.snapshot()["states"]
            p = placements()
            return all(
                n in s
                and s[n]["connected"]
                and s[n]["session"] != previous
                and p[n]["session"] == s[n]["session"]
                and s[n]["mode"] == "paused"
                for n in ("mira", "orren")
            )

        app.start()
        try:
            process = start()
            if world_managed:
                wait_for(
                    lambda: app.snapshot()["states"].get("orren", {}).get("connected")
                )
                time.sleep(5)
                assert "mira" not in app.snapshot()["states"]
                assert placements()["orren"]["session"] == "previous"
                print(
                    "PASS world-created NPC bound; old saved placements were neither restored nor overwritten",
                    flush=True,
                )
                st = app.snapshot()["states"]["orren"]
                command = dict(
                    placements()["mira"],
                    kind="restore",
                    session=st["session"],
                    expires=st["tick"] + 5,
                    request="forbidden",
                )
                app.pending["forbidden"] = dict(
                    npc="mira", kind="restore", time=time.monotonic()
                )
                app.redis.call("RPUSH", prefix + ":commands", json.dumps(command))
                wait_for(lambda: "forbidden" not in app.pending)
                assert "mira" not in app.snapshot()["states"] and app.error.startswith(
                    "NPC restoration failed"
                )
                print(
                    "PASS game refused restoration even when a command was injected directly",
                    flush=True,
                )
                # Separate game callbacks reflect actual despawn/respawn events;
                # a single giant loop can exhaust NWScript's instruction budget.
                code = (
                    'object n=StringToObject("'
                    + st["object"]
                    + '");ExecuteScript("rw_unbind",n);ExecuteScript("rw_bind",n);'
                )
                for cycle in range(40):
                    os.write(fd, ("eval " + code + "\n").encode())
                    wait_for(
                        lambda: app.snapshot()["states"]["orren"]["epoch"]
                        >= st["epoch"] + 2 * (cycle + 1)
                    )
                wait_for(
                    lambda: app.snapshot()["states"]["orren"]["epoch"]
                    >= st["epoch"] + 80
                )
                print(
                    "PASS world integration reused a binding slot through 40 detach/rebind cycles",
                    flush=True,
                )
                return
            wait_for(lambda: restored("previous"))
            wait_for(lambda: abs(placements()["orren"]["x"] - 24.0) < 0.2)
            print(
                "PASS spawned NPC restored and existing creature rebound at saved coordinates",
                flush=True,
            )
            state = app.snapshot()["states"]["mira"]
            command = dict(
                placements()["mira"],
                kind="restore",
                session=state["session"],
                expires=state["tick"] + 5,
                request="duplicate",
                x=30.0,
            )
            app.redis.call("RPUSH", prefix + ":commands", json.dumps(command))
            time.sleep(2)
            assert app.snapshot()["states"]["mira"]["object"] == state["object"]
            assert abs(placements()["mira"]["x"] - 25.0) < 0.2
            print(
                "PASS duplicate restore did not move or replace an existing binding",
                flush=True,
            )
            object_id = app.snapshot()["states"]["orren"]["object"]
            code = (
                'object n=StringToObject("'
                + object_id
                + '");AssignCommand(n,JumpToLocation(Location(GetArea(n),Vector(22.0,14.0,0.0),180.0)));'
            )
            os.write(fd, ("eval " + code + "\n").encode())
            wait_for(lambda: abs(placements()["orren"]["x"] - 22.0) < 0.2)
            print(
                "PASS moved creature's new location was saved automatically", flush=True
            )
            previous = app.snapshot()["states"]["mira"]["session"]
            process.terminate()
            process.wait(timeout=15)
            process = start()
            wait_for(lambda: restored(previous))
            wait_for(lambda: abs(placements()["orren"]["x"] - 22.0) < 0.2)
            assert abs(placements()["mira"]["x"] - 25.0) < 0.2
            print(
                "PASS second native restart restored both NPCs, including moved bound creature, paused",
                flush=True,
            )
        finally:
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
            app.running = False
            app.pool.shutdown(wait=True)
            time.sleep(0.2)
            app.redis.call("DEL", prefix + ":events", prefix + ":commands")
            app.store.db.close()
            os.close(fd)
            log.close()


if __name__ == "__main__":
    main()
