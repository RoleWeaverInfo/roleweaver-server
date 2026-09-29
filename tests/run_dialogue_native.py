"""Isolated NWN engine test; never installs files in the live server.

Requires a matching test build of NWNX_RWTranslation, nwnsc and a prepared demo
module containing rw_base and rw_tr_guide. Network recipients are simulated by
the test-only plugin; checking actual client rendering is a separate playtest.
"""

import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.dialogue_preparation_native import build_fixture
from tools.module_copy import resources, replace_resref, simple_fields


def run(args):
    sandbox = Path(tempfile.mkdtemp(prefix="rw-dialogue-native-"))
    override = sandbox / "override"
    (sandbox / "modules").mkdir()
    override.mkdir()
    plugins = sandbox / "plugins"
    plugins.mkdir()
    for name in ("Core", "Dialog", "Util", "Player"):
        (plugins / f"NWNX_{name}.so").symlink_to(
            args.nwnx / "plugins" / f"NWNX_{name}.so"
        )
    (plugins / "NWNX_RWTranslation.so").symlink_to(args.plugin)
    build_fixture(override)
    shutil.copy2(
        ROOT / "tests/dialogue_preparation_native.nss", override / "invtest.nss"
    )
    # Prefer freshly compiled bridge code over any older module resources.
    for source in args.scripts.glob("*.ncs"):
        shutil.copy2(source, override / source.name)
    for source in override.glob("*.nss"):
        result = subprocess.run(
            [
                str(args.compiler),
                "-n",
                str(args.runtime),
                "-i",
                f"{override};{args.scripts};{args.nwnx / 'nwscripts'}",
                str(source),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    raw = args.module.read_bytes()
    entries = resources(raw)
    for i, (name, kind, data) in enumerate(entries):
        if (name, kind) == ("module", 2014):
            for label in simple_fields(data):
                if label.startswith("Mod_On"):
                    data, _ = replace_resref(
                        data, label, "invtest" if label == "Mod_OnModLoad" else ""
                    )
            entries[i] = name, kind, data
    size, offset = struct.unpack_from("<I4xI", raw, 12)
    localized = raw[offset : offset + size]
    header = bytearray(raw[:160])
    count = len(entries)
    ko = 160 + len(localized)
    ro, do = ko + count * 24, ko + count * 32
    struct.pack_into("<I", header, 16, count)
    struct.pack_into("<III", header, 20, 160, ko, ro)
    keys, index, payload = bytearray(), bytearray(), bytearray()
    for i, (name, kind, data) in enumerate(entries):
        keys.extend(struct.pack("<16sIHH", name.encode(), i, kind, 0))
        index.extend(struct.pack("<II", do + len(payload), len(data)))
        payload.extend(data)
    (sandbox / "modules/test.mod").write_bytes(
        header + localized + keys + index + payload
    )
    # Do not inherit a live world's plugin configuration or Redis credentials.
    env = {k: v for k, v in os.environ.items() if not k.startswith("NWNX_")}
    env.update(
        LD_PRELOAD=str(plugins / "NWNX_Core.so"),
        NWNX_CORE_LOAD_PATH=str(plugins),
        NWNX_CORE_SKIP_ALL="1",
    )
    for name in ("DIALOG", "UTIL", "PLAYER", "RWTRANSLATION"):
        env[f"NWNX_{name}_SKIP"] = "n"

    def logs():
        return "\n".join(
            p.read_text(errors="replace") for p in sandbox.rglob("*.txt")
        ) + (sandbox / "console.log").read_text(errors="replace")

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
            ],
            cwd=args.runtime / "bin/linux-x86",
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(120):
                if "RW_INV_TEST FINISHED" in logs() or process.poll() is not None:
                    break
                time.sleep(0.25)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    output = logs()
    print(
        "\n".join(
            line
            for line in output.splitlines()
            if "RW_INV_TEST" in line or "error" in line.lower()
        )
    )
    print("Isolated test artifacts:", sandbox)
    if (
        "RW_INV_TEST FINISHED" not in output
        or "native_entry_recipient_text_and_arguments PASS" not in output
        or any("RW_INV_TEST" in line and "FAIL" in line for line in output.splitlines())
    ):
        raise RuntimeError("Native tests failed; see isolated logs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("module", "scripts", "runtime", "nwnx", "compiler", "plugin"):
        parser.add_argument(
            "--" + name,
            type=lambda value: Path(value).expanduser().resolve(),
            required=True,
        )
    parser.add_argument("--port", type=int, default=5199)
    run(parser.parse_args())
