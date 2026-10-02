"""Create a world-specific review bundle without writing to NWN's resources."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import install_profile as profiles
from build_addon import audit
from prepare_addon import ENTRIES
from setup_addon import prepare_import, write_erf


def prepare(p):
    profiles.validate(p)
    output = (
        profiles.ROOT / "builds" / (p["world_id"] + "-setup-" + str(time.time_ns()))
    )
    for key in ("runtime", "plugins", "headers", "server_home"):
        existing = Path(p["paths"][key]).resolve()
        if output.resolve().is_relative_to(existing):
            raise ValueError(
                "Extract the package outside the existing NWN/server/plugin folders before preparing files"
            )
    report = audit(Path(p["paths"]["module"]), [Path(v) for v in p["resources"]])
    prepare_import(
        dict(
            world_id=p["world_id"],
            redis_prefix=p["redis_prefix"],
            nwnx_headers=Path(p["paths"]["headers"]),
            output=output,
        )
    )
    scripts = output / "scripts"
    flags = p["features"]
    load = scripts / "rw_userload.nss"
    text = load.read_text()
    for name, flag in (
        ("rw_allow_dm_spawn", "dm_spawn"),
        ("rw_allow_persistent_spawn", "persistent_spawn"),
    ):
        text = text.replace(
            f'"{name}", FALSE', f'"{name}", {"TRUE" if flags[flag] else "FALSE"}'
        )
    load.write_text(text)
    compiler = p["paths"]["compiler"]
    if compiler:
        for name in (*ENTRIES, "rw_userload", "rw_userchat"):
            try:
                subprocess.run(
                    [
                        compiler,
                        "-n",
                        p["paths"]["runtime"],
                        "-i",
                        str(scripts),
                        str(scripts / (name + ".nss")),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except subprocess.CalledProcessError as exc:
                (output / "compiler.log").write_bytes(
                    (exc.stdout or b"") + (exc.stderr or b"")
                )
                raise ValueError(
                    f"Could not compile {name}. See {output / 'compiler.log'}; the server is unchanged."
                ) from None
            shutil.move(
                str(scripts / (name + ".ncs")), output / "compiled" / (name + ".ncs")
            )
    write_erf(
        output / "RoleWeaver-Import.erf",
        [
            *scripts.glob("*.nss"),
            *(output / "compiled").glob("*.ncs"),
            *(output / "optional-assets").glob("*.utc"),
            *(output / "optional-assets").glob("*.utm"),
        ],
    )
    (output / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "AURORA.md").write_bytes((profiles.ROOT / "addon/AURORA.md").read_bytes())
    selected = (
        ", ".join(k.replace("_", " ") for k, value in flags.items() if value)
        or "basic AI NPC conversations"
    )
    guide = f"""# Connect {p['world_id']} to Role Weaver

Selected features: {selected}. These are preparation choices, not proof that a feature is enabled.
Module: `{p['paths']['module']}`. Server home: `{p['paths']['server_home']}`.
NWN runtime: `{p['paths']['runtime']}`. NWNX plugins: `{p['paths']['plugins']}`.
World ID: `{p['world_id']}`. Redis: `127.0.0.1:{p['redis_port']}`, prefix `{p['redis_prefix']}`.

## 1. Review your existing events

Detected event assignments:
```json
{json.dumps(report['module_hooks'], indent=2)}
```
`review.json` lists possible resource collisions and chat registrations. Existing Role Weaver
resources may be an earlier integration; compare them before importing. Supplied loose resource
folders were inspected; HAK archives and arbitrary custom systems were not. File inspection
cannot prove which script is used at runtime or whether chat moderation permits a message.

## 2. Add the resources using ONE method

**Aurora:** back up your module, open a working copy with its required HAK/TLK files, and
import `{output / 'RoleWeaver-Import.erf'}`. See `AURORA.md` beside this file for menu instructions.
Do not replace customised NWNX headers without comparing them with the matching installed build.

**Existing build pipeline:** use `scripts/`, `compiled/` and the needed `optional-assets/`
through your normal resource packaging. Do not install another copy into override if you
already imported them into the module. Compiled bridge files: **{'included' if compiler else 'not included; compile in Aurora or configure nwnsc'}**.

## 3. Preserve your existing handlers

Inside your existing OnModuleLoad main(), after normal initialization:
```c
ExecuteScript("rw_init", GetModule());
SetLocalInt(GetModule(), "rw_allow_dm_spawn", {'TRUE' if flags['dm_spawn'] else 'FALSE'});
SetLocalInt(GetModule(), "rw_allow_persistent_spawn", {'TRUE' if flags['persistent_spawn'] else 'FALSE'});
```
Inside the approved public-message path of OnPlayerChat, after moderation/privacy decisions:
```c
ExecuteScript("rw_modulechat", OBJECT_SELF);
```
If your world instead owns an NWNX Chat callback, call `rw_chat` inside that callback's approved
message path. Choose exactly one route. Do not wrap an unknown chat handler and forward all
messages after it. Only empty/new module events should use `rw_userload` and `rw_userchat`.

Compile changed handlers, save, and deploy with your existing server workflow. This setup has
not changed the module, launcher, plugins or running NWN process.

## 4. Check plugins and selected features

Use NWNX binaries and headers matching your server build. Required plugins: {', '.join(profiles.PLUGINS)}.
Keep existing plugins. Chat must be enabled (`NWNX_CHAT_SKIP=n`). NWNX Redis must use the same
local port shown above. Review shared Redis users before changing its endpoint.

- NPCs: bind a test creature to one profile, then Resume in the dashboard.
- Companions: enable in the Companions dashboard; players opt in with `/rw companion on`.
- DM spawning/encounters: the two module flags above must agree with installed config
  `allow_dm_spawn` / `allow_persistent_spawn`. Fresh installs use these choices; updates preserve
  existing settings. Authorize actions/encounters separately in the dashboard.
- Merchants: import `rw_shop.utm`, authorize shop actions for the NPC, and check coexistence
  with your world's shop/price scripts. Selecting this feature does not grant every NPC shop access.
- Translation: basic text translation and standard-dialogue preparation have separate requirements.
  For dialogues use `bash setup.sh dialogues --world {p['world_id']}`; the helper reuses these paths.
  Multiplayer dialogue translation also needs the matching native adapter; use
  `bash setup.sh adapter --world {p['world_id']}`. Current adapter target: Linux x86-64 8193.37-17.
  Preparation makes no translation/model calls. Enable translation after checking the installed adapter.

## 5. Restart and verify

Restart NWN using YOUR normal launcher/service during your maintenance window. This installer
does not know how every persistent world is managed and will not restart NWN itself.
From any newly extracted Role Weaver package run:
```bash
bash setup.sh verify --world {p['world_id']}
```
Dashboard: http://127.0.0.1:{p['dashboard_port']}/ . From Windows, open an SSH tunnel:
```text
ssh -N -L {p['dashboard_port']}:127.0.0.1:{p['dashboard_port']} YOUR_UBUNTU_USER@YOUR_SERVER_IP
```
Create a test NPC profile, bind it and check a player conversation in offline mode before adding
your provider in LLM Settings. Check existing chat filtering, DM takeover and native companion controls.
Successful health checks establish connectivity, not complete gameplay compatibility.

## Undo module integration

Restore your backed-up module/handlers and only the resources you replaced through your normal
deployment process. Preserve shared plugins/Redis. `bash setup.sh rollback` reverts a managed
Role Weaver software update only; it does not revert NWN/module files or rewind player data.
"""
    (output / "INSTALL.md").write_text(guide, encoding="utf-8")
    manifest = dict(
        world_id=p["world_id"],
        redis_prefix=p["redis_prefix"],
        compiled=bool(compiler),
        files={
            path.relative_to(output)
            .as_posix(): hashlib.sha256(path.read_bytes())
            .hexdigest()
            for path in output.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        },
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    p["progress"].update(bundle=str(output), bundle_signature=profiles.signature(p))
    profiles.save(p)
    return output


def current(p):
    """Never silently reuse partial/tampered output or a previous package's bridge."""
    try:
        output = Path(p["progress"]["bundle"])
        manifest = json.loads((output / "manifest.json").read_text())
        return (
            p["progress"].get("bundle_signature") == profiles.signature(p)
            and bool(manifest["files"])
            and all(
                not Path(name).is_absolute()
                and ".." not in Path(name).parts
                and hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
                for name, digest in manifest["files"].items()
            )
        )
    except (OSError, ValueError, KeyError):
        return False
