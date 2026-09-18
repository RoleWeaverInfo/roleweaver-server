"""Prepare bridge scripts for an existing world without reading or copying its module.

Output is a review bundle only. This tool never writes into the server's runtime,
module, override directory, or scripts tree and never starts/stops a server.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from build_addon import settings, ENTRY_SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = tuple(name for name in ENTRY_SCRIPTS if name != "rw_load")
INCLUDES = (
    "rw_inc",
    "rw_chat_inc",
    "rw_creature",
    "rw_talk_inc",
    "rw_actions",
    "rw_merchant",
    "rw_stock",
)
HEADERS = ("core", "chat", "events", "redis", "creature", "player")


def prepare(
    output, world, prefix, runtime=None, includes=None, compiler=None, source_only=False
):
    generated = settings(world, prefix, "world", "manual")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError(
            "Choose a new output directory; existing bundles are never overwritten"
        )
    if not source_only:
        if not all((runtime, includes, compiler)):
            raise ValueError(
                "Supply --runtime, --includes and --compiler, or use --source-only"
            )
        runtime, includes, compiler = (
            Path(runtime).resolve(),
            Path(includes).resolve(),
            Path(compiler).resolve(),
        )
        if not compiler.is_file() or not os.access(compiler, os.X_OK):
            raise ValueError("Compiler is missing or not executable: " + str(compiler))
        if not list((runtime / "data").glob("*.key")) or not list(
            (runtime / "data").glob("*.bif")
        ):
            raise ValueError(
                "--runtime must contain the existing NWN data/*.key and data/*.bif resources"
            )
        for name in HEADERS:
            if not (includes / ("nwnx_" + name + ".nss")).is_file():
                raise ValueError("Missing matching NWNX header: nwnx_" + name + ".nss")
        for dependency in (runtime, includes, compiler):
            if output == dependency or dependency in output.parents:
                raise ValueError(
                    "Choose an output folder outside the existing runtime/header/compiler locations"
                )
    output.mkdir(parents=True)
    source = output / "scripts"
    source.mkdir()
    for name in (*ENTRIES, *INCLUDES):
        shutil.copy2(ROOT / "bridge" / (name + ".nss"), source / (name + ".nss"))
    (source / "rw_settings.nss").write_text(generated, encoding="utf-8")
    # Manual ownership: never register a second NWNX Chat callback.
    init = source / "rw_init.nss"
    init.write_text(
        init.read_text().replace(
            '    if (RW_REGISTERS_CHAT) NWNX_Chat_RegisterChatScript("rw_chat");\n', ""
        )
    )
    compiled = output / "compiled"
    compiled.mkdir()
    if not source_only:
        for name in ENTRIES:
            subprocess.run(
                [
                    str(compiler),
                    "-n",
                    str(runtime),
                    "-i",
                    str(includes) + ";" + str(source),
                    str(source / (name + ".nss")),
                ],
                check=True,
                timeout=30,
                capture_output=True,
            )
            shutil.move(str(source / (name + ".ncs")), compiled / (name + ".ncs"))
    shutil.copytree(ROOT / "assets", output / "optional-assets")
    config = json.loads((ROOT / "config.example.json").read_text())
    config.update(
        world_id=world,
        world_name=world,
        redis_prefix=prefix,
        placement_owner="world",
        allow_dm_spawn=False,
        allow_persistent_spawn=False,
    )
    (output / "service-config.example.json").write_text(
        json.dumps(config, indent=2) + "\n"
    )
    guide = (ROOT / "addon/INTEGRATION.md").read_text(encoding="utf-8")
    (output / "INSTALL.md").write_text(
        f"# Prepared bridge for {world}\n\nRedis prefix: `{prefix}`. "
        + (
            "Source only: compile these scripts in your normal toolchain.\n\n"
            if source_only
            else "Compiled bridge scripts are available in compiled/.\n\n"
        )
        + guide,
        encoding="utf-8",
    )
    manifest = dict(
        world_id=world,
        redis_prefix=prefix,
        placement_owner="world",
        chat_ownership="existing_world",
        compiled=not source_only,
        files={},
    )
    manifest["files"] = {
        str(p.relative_to(output))
        .replace("\\", "/"): hashlib.sha256(p.read_bytes())
        .hexdigest()
        for p in output.rglob("*")
        if p.is_file()
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world-id", required=True)
    p.add_argument("--redis-prefix", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--runtime", type=Path, help="Existing NWN runtime resource root; read only"
    )
    p.add_argument(
        "--includes", type=Path, help="Existing matching NWNX .nss headers; read only"
    )
    p.add_argument("--compiler", type=Path, help="Existing nwnsc executable")
    p.add_argument("--source-only", action="store_true")
    a = p.parse_args()
    prepare(
        a.output,
        a.world_id,
        a.redis_prefix,
        a.runtime,
        a.includes,
        a.compiler,
        a.source_only,
    )
    print("Review bundle ready:", a.output)
    print("No module was read or copied. No existing server files were changed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print("Preparation stopped:", e)
        if isinstance(e, subprocess.CalledProcessError):
            print(
                (e.stdout or b"").decode(errors="replace")
                if isinstance(e.stdout, bytes)
                else e.stdout or ""
            )
        raise SystemExit(1)
