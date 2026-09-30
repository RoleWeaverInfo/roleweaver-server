"""Check demo doors and walkability in a private, temporary NWN server instance.

Run on Linux with --runtime /path/to/nwserver --compiler /path/to/nwnsc
--module /path/to/YourWorld_Fixed.mod. Does not load NWNX or contact the live
Role Weaver service. Leaves the isolated server log directory for inspection.
"""

import argparse
import os
from pathlib import Path
import secrets
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
    sandbox = Path(tempfile.mkdtemp(prefix="rw-demo-areas-"))
    (sandbox / "modules").mkdir()
    override = sandbox / "override"
    override.mkdir()
    source = override / "areaprobe.nss"
    source.write_bytes((ROOT / "tests/demo_areas_native.nss").read_bytes())
    subprocess.run(
        [str(args.compiler), "-n", str(args.runtime), str(source)], check=True
    )
    raw = args.module.read_bytes()
    entries = {(n, k): b for n, k, b in resources(raw)}
    # Disable gameplay event hooks only in the disposable test copy.
    signature, module = read(entries["module", 2014])
    for label, (kind, _) in module[1].items():
        if label.startswith("Mod_On"):
            module[1][label] = kind, b"areaprobe" if label == "Mod_OnModLoad" else b""
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
    env = {k: v for k, v in os.environ.items() if not k.startswith("NWNX_")}
    env.pop("LD_PRELOAD", None)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", args.port))  # Refuse an already occupied test port.

    def logs():
        paths = list(sandbox.rglob("*.txt")) + [sandbox / "console.log"]
        return "\n".join(p.read_text(errors="replace") for p in paths if p.is_file())

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
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                output = logs()
                if "RW_AREA_TEST FINISHED" in output or process.poll() is not None:
                    break
                time.sleep(0.5)
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    output = logs()
    checks = sorted(
        {
            line[line.index("RW_AREA_TEST") :]
            for line in output.splitlines()
            if "RW_AREA_TEST" in line
        }
    )
    print("\n".join(checks))
    print(f"Isolated test logs: {sandbox}")
    passed = sum(line.endswith(" PASS") for line in checks)
    if (
        "RW_AREA_TEST FINISHED" not in checks
        or passed != 12
        or any(line.endswith(" FAIL") for line in checks)
    ):
        raise SystemExit("Native area test failed or did not finish; inspect its logs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--port", type=int, default=5198)
    run(parser.parse_args())
