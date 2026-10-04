"""Exercise familiar hearing in a private disposable NWN/NWNX world.

Only player and association lookup use synthetic creatures. No real client,
account, live service, Redis queue or production module is used. NWN executes
the real buffer, privacy, appearance, audibility and public speech paths.
"""

import argparse
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.expand_demo_world import pack_module
from tools.gff import read, write
from tools.module_copy import resources


def run(args):
    sandbox = Path(tempfile.mkdtemp(prefix="rw-companion-hearing-"))
    (sandbox / "modules").mkdir()
    override = sandbox / "override"
    shutil.copytree(ROOT / "bridge", override)
    hearing = (override / "rw_hearing.nss").read_text()
    hearing = (
        hearing.replace("GetIsPC(owner)", 'GetLocalInt(owner,"fixture_pc")')
        .replace("GetIsPC(speaker)", 'GetLocalInt(speaker,"fixture_pc")')
        .replace("GetMaster(familiar)", 'GetLocalObject(familiar,"fixture_master")')
        .replace("GetFirstPC()", 'GetLocalObject(GetModule(),"fixture_owner")')
        .replace("GetNextPC()", "OBJECT_INVALID")
    )
    (override / "rw_hearing.nss").write_text(hearing)
    base = (override / "rw_cp_base.nss").read_text()
    assert "return GetAssociate(ASSOCIATE_TYPE_FAMILIAR,owner);" in base
    (override / "rw_cp_base.nss").write_text(
        base.replace(
            "return GetAssociate(ASSOCIATE_TYPE_FAMILIAR,owner);",
            'return GetLocalObject(owner,"fixture_familiar");',
        )
    )
    shutil.copy2(
        ROOT / "tests/companion_hearing_native.nss", override / "hearprobe.nss"
    )
    for name in ("hearprobe", "rw_hear"):
        result = subprocess.run(
            [
                str(args.compiler),
                "-n",
                str(args.runtime),
                "-i",
                f"{override};{args.nwnx / 'nwscripts'}",
                str(override / (name + ".nss")),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    raw = args.module.read_bytes()
    entries = {(n, k): b for n, k, b in resources(raw)}
    signature, module = read(entries["module", 2014])
    for label, (kind, _) in module[1].items():
        if label.startswith("Mod_On"):
            module[1][label] = kind, b"hearprobe" if label == "Mod_OnModLoad" else b""
    entries["module", 2014] = write(signature, module)
    for key, data in list(entries.items()):
        if key[1] == 2023:
            signature, placed = read(data)
            placed[1]["Creature List"] = 15, []
            entries[key] = write(signature, placed)
    signature, creature = read(entries["rw_base", 2027])
    for label, (kind, _) in creature[1].items():
        if label.startswith("Script"):
            creature[1][label] = kind, b""
    entries["rw_base", 2027] = write(signature, creature)
    (sandbox / "modules/test.mod").write_bytes(pack_module(raw, entries))
    plugins = sandbox / "plugins"
    plugins.mkdir()
    for name in ("Core", "Chat"):
        (plugins / f"NWNX_{name}.so").symlink_to(
            args.nwnx / "plugins" / f"NWNX_{name}.so"
        )
    env = {k: v for k, v in os.environ.items() if not k.startswith("NWNX_")}
    env.update(
        LD_PRELOAD=str(plugins / "NWNX_Core.so"),
        NWNX_CORE_LOAD_PATH=str(plugins),
        NWNX_CORE_SKIP_ALL="1",
        NWNX_CHAT_SKIP="n",
    )
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", args.port))

    def logs():
        return "\n".join(
            p.read_text(errors="replace")
            for p in list(sandbox.rglob("*.txt")) + [sandbox / "console.log"]
            if p.is_file()
        )

    with (sandbox / "console.log").open("w") as log:
        process = subprocess.Popen(
            [
                str(args.runtime / "bin/linux-x86/nwserver-linux"),
                "-userdirectory",
                str(sandbox),
                "-module",
                "test",
                "-port",
                str(args.port),
                "-publicserver",
                "0",
                "-maxclients",
                "1",
                "-reloadwhenempty",
                "0",
                "-playerpassword",
                secrets.token_hex(16),
                "-dmpassword",
                secrets.token_hex(16),
            ],
            cwd=args.runtime / "bin/linux-x86",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if "RW_HEARING_TEST FINISHED" in logs() or process.poll() is not None:
                    break
                time.sleep(0.5)
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    checks = sorted(
        {
            line[line.index("RW_HEARING_TEST") :]
            for line in logs().splitlines()
            if "RW_HEARING_TEST" in line
        }
    )
    print("\n".join(checks))
    print("Isolated test logs:", sandbox)
    if "RW_HEARING_TEST FINISHED" not in checks or any(
        "FAIL" in line for line in checks
    ):
        raise SystemExit("Native hearing checks failed or did not finish")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("runtime", "compiler", "module", "nwnx"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, default=5197)
    run(parser.parse_args())
