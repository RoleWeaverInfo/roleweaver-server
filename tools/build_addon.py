"""Build a reviewable add-on bundle. Never modifies or restarts an existing server."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from module_copy import make_copy, resources, simple_fields

ENTRY_SCRIPTS = (
    "rw_init",
    "rw_chat",
    "rw_modulechat",
    "rw_possess",
    "rw_tick",
    "rw_bind",
    "rw_unbind",
    "rw_talk",
    "rw_shop_evt",
    "rw_load",
)


def check_dependencies(base, native, scripts=()):
    missing = []
    compiler = base / "tools/nwnsc"
    if not compiler.is_file():
        missing.append("tools/nwnsc: install or link the Linux NWScript compiler")
    elif not os.access(compiler, os.X_OK):
        missing.append(
            "tools/nwnsc: make the compiler executable with chmod +x tools/nwnsc"
        )
    if not list((native / "runtime/data").glob("*.key")) or not list(
        (native / "runtime/data").glob("*.bif")
    ):
        missing.append(
            str(native / "runtime/data")
            + ": link or copy the installed NWN runtime resources"
        )
    for name in (
        "nwnx_core.nss",
        "nwnx_chat.nss",
        "nwnx_events.nss",
        "nwnx_redis.nss",
        "nwnx_creature.nss",
        "nwnx_player.nss",
    ):
        if not (native / "nwscripts" / name).is_file():
            missing.append(
                str(native / "nwscripts" / name)
                + ": link or copy the installed NWNX includes"
            )
    for directory in scripts:
        if not directory.is_dir():
            missing.append(
                str(directory) + ": scripts directory missing; omit --scripts if unused"
            )
    if missing:
        raise ValueError(
            "Missing build dependencies (no output created):\n- " + "\n- ".join(missing)
        )


def settings(world, prefix, owner="world", chat="manual"):
    for value in (world, prefix):
        if not re.fullmatch(r"[a-zA-Z0-9_:-]{1,80}", value):
            raise ValueError(
                "World ID and Redis prefix must use letters, digits, underscores, colons or hyphens"
            )
    if owner not in ("world", "roleweaver") or chat not in (
        "manual",
        "exclusive",
        "module",
    ):
        raise ValueError("Invalid ownership settings")
    return (
        f'const string RW_WORLD = "{world}";\nconst string RW_REDIS_PREFIX = "{prefix}";\n'
        f'const int RW_OWNS_PLACEMENTS = {int(owner == "roleweaver")};\n'
        f'const int RW_REGISTERS_CHAT = {int(chat == "exclusive")};\n'
    )


def audit(module, scripts=()):
    raw = module.read_bytes()
    entries = resources(raw)
    hooks = simple_fields(
        next(data for name, kind, data in entries if name == "module" and kind == 2014)
    )
    blobs = [
        (name + (".nss" if kind == 2009 else ".ncs"), data)
        for name, kind, data in entries
        if kind in (2009, 2010)
    ]
    # NWN resource types: NSS 2009, NCS 2010.
    for directory in scripts:
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".nss", ".ncs"):
                blobs.append((str(path.resolve()), path.read_bytes()))
    hits = sorted(name for name, data in blobs if b"RegisterChatScript" in data)
    reserved = set(ENTRY_SCRIPTS) | {
        "rw_inc",
        "rw_settings",
        "rw_chat_inc",
        "rw_playerchat",
        "rw_creature",
        "rw_talk_inc",
        "rw_actions",
        "rw_merchant",
        "rw_stock",
        "rw_shop",
        "rw_base",
    }
    collisions = sorted(
        name
        for name, kind, _ in entries
        if name in reserved and kind in (2009, 2010, 2027)
    )
    collisions += sorted(
        name
        for name, _ in blobs
        if Path(name).is_absolute() and Path(name).stem in reserved
    )
    return {
        "source_module": str(module.resolve()),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "module_hooks": {k: v for k, v in hooks.items() if k.startswith("Mod_On")},
        "possible_chat_registrations": hits,
        "reserved_resource_collisions": collisions,
        "scripts_inspected": len(blobs),
        "limits": "Static inspection cannot prove runtime ownership. Include override/HAK sources, startup scripts and custom plugins in administrator review.",
    }


def build(module, output, native, world, prefix, owner, chat, scripts=()):
    if output.exists():
        raise ValueError(
            "Choose a new output directory; existing bundles are never overwritten"
        )
    generated_settings = settings(world, prefix, owner, chat)
    report = audit(module, scripts)
    if report["reserved_resource_collisions"]:
        raise ValueError(
            "Module contains reserved Role Weaver resources; use manual source integration"
        )
    if chat == "exclusive" and report["possible_chat_registrations"]:
        raise ValueError(
            "Existing chat registration detected. Use manual integration and preserve its handler"
        )
    base = Path(__file__).resolve().parent.parent
    check_dependencies(base, native, scripts)
    output.mkdir(parents=True)
    (output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    source = output / "bridge"
    source.mkdir()
    for name in (
        *ENTRY_SCRIPTS,
        "rw_inc",
        "rw_chat_inc",
        "rw_creature",
        "rw_talk_inc",
        "rw_actions",
        "rw_merchant",
        "rw_stock",
    ):
        path = base / "bridge" / (name + ".nss")
        if path.exists():
            shutil.copy2(path, source / path.name)
    (source / "rw_settings.nss").write_text(generated_settings)
    if chat != "exclusive":
        init = source / "rw_init.nss"
        init.write_text(
            init.read_text().replace(
                '    if (RW_REGISTERS_CHAT) NWNX_Chat_RegisterChatScript("rw_chat");\n',
                "",
            )
        )
    revised_module = output / "module" / module.name
    original = make_copy(
        module,
        revised_module,
        chat_script="rw_playerchat" if chat == "module" else None,
    )
    wrapper = "void main() {\n"
    if original:
        wrapper += '    ExecuteScript("' + original + '", OBJECT_SELF);\n'
    wrapper += '    ExecuteScript("rw_init", GetModule());\n}\n'
    (source / "rw_load.nss").write_text(wrapper)
    entries = list(ENTRY_SCRIPTS)
    if chat == "module":
        original_chat = report["module_hooks"].get("Mod_OnPlrChat", "")
        wrapper = "void main() {\n"
        if original_chat:
            wrapper += '    ExecuteScript("' + original_chat + '", OBJECT_SELF);\n'
        wrapper += '    ExecuteScript("rw_modulechat", OBJECT_SELF);\n}\n'
        (source / "rw_playerchat.nss").write_text(wrapper)
        entries.append("rw_playerchat")
    compiled = output / "compiled"
    compiled.mkdir()
    for name in entries:
        subprocess.run(
            [
                str(base / "tools/nwnsc"),
                "-n",
                str(native / "runtime"),
                "-i",
                str(native / "nwscripts") + ";" + str(source),
                str(source / (name + ".nss")),
            ],
            check=True,
            timeout=15,
            capture_output=True,
        )
        shutil.move(str(source / (name + ".ncs")), compiled / (name + ".ncs"))
    shutil.copy2(base / "assets/rw_base.utc", compiled / "rw_base.utc")
    shutil.copy2(base / "assets/rw_shop.utm", compiled / "rw_shop.utm")
    config = json.loads((base / "config.example.json").read_text())
    config.update(placement_owner=owner, redis_prefix=prefix, world_id=world)
    (output / "service-config.example.json").write_text(
        json.dumps(config, indent=2) + "\n"
    )
    manifest = {
        "world_id": world,
        "placement_owner": owner,
        "chat_mode": chat,
        "source_module_sha256": report["source_sha256"],
        "files": {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.rglob("*")
            if p.is_file()
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "INSTALL.md").write_text(f"""# Reviewed add-on installation

This bundle contains no dedicated NWN server. Use the world's existing server.
World: `{world}`. Placement owner: `{owner}`. Chat mode: `{chat}`.

1. Review audit.json and INTEGRATION.md in the Role Weaver source distribution.
   Static inspection is incomplete; review HAKs, overrides and runtime plugins too.
2. Back up your active module and any files you intend to change.
3. Merge bridge sources into the world's build, or stage all files from compiled/ (including .ncs, .utc and .utm assets) in its
   resource directory. The module/ copy preserves the original OnModuleLoad handler
   and calls rw_init afterward. It is optional: integrating that call into your own
   load handler is preferable when you maintain the world's source.
4. In manual chat mode, keep your existing NWNX Chat owner. After its moderation
   and privacy checks, call ExecuteScript("rw_chat", OBJECT_SELF) from that NWNX
   Chat callback. rw_chat cannot be called from an ordinary OnPlayerChat callback.
   If no NWNX chat owner exists, review and rebuild with --chat-mode exclusive.
   In module chat mode, the revised module instead runs the original OnPlayerChat
   handler first, then rw_modulechat with its resulting message. No NWNX chat
   callback is registered and no manual chat hook is needed for that mode.
5. Install the separate companion following INSTALL_COMPANION.md in the source
   distribution. Match the world ID, Redis prefix and placement ownership in
   service-config.example.json.
   Supply its API key privately. Create the NPC profiles in its dashboard.
6. From your world's existing creature spawn/load code, set local string rw_profile
   to the profile ID and ExecuteScript("rw_bind", npc). Call rw_unbind before reusing
   or removing a creature. No NPC is automatically seeded by this bundle.
7. On a staging copy, verify original chat behavior, NPC binding, DM possession,
   reloads, and removal before installing during your normal maintenance window.

Rollback: restore your original load/chat handlers and module, remove only the
Role Weaver resources listed in manifest.json that you installed, and restart the
game to clear registered callbacks. Stop the separate Role Weaver service. Keep its
database if you want to retain memories. Do not remove Redis if other systems use it.

The builder did not install files, change your server configuration or restart it.
""")
    manifest["files"] = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--module", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--native", required=True, type=Path)
    p.add_argument("--world-id", required=True)
    p.add_argument("--redis-prefix", required=True)
    p.add_argument(
        "--placement-owner", choices=("world", "roleweaver"), default="world"
    )
    p.add_argument(
        "--chat-mode", choices=("manual", "exclusive", "module"), default="manual"
    )
    p.add_argument("--scripts", type=Path, action="append", default=[])
    args = p.parse_args()
    try:
        build(
            args.module,
            args.output,
            args.native,
            args.world_id,
            args.redis_prefix,
            args.placement_owner,
            args.chat_mode,
            args.scripts,
        )
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print("Build stopped: " + str(exc), file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(
                (
                    (exc.stdout or b"").decode(errors="replace")
                    if isinstance(exc.stdout, bytes)
                    else (exc.stdout or "")
                ),
                file=sys.stderr,
            )
        sys.exit(1)
    print("Reviewable add-on bundle created:", args.output)
