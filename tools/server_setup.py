"""One resumable existing-server workflow, also callable as setup.sh commands."""

import json
from pathlib import Path
import subprocess
import time
import urllib.request

import install_profile as profiles
import install_bundle as bundles
import manage_installation as manager
import setup_wizard as ui


def choose_world(world=None, configure=False):
    if world:
        return profiles.identifier(world)
    found = sorted(p.stem for p in profiles.profile_directory().glob("*.json"))
    if len(found) == 1 and not configure:
        return found[0]
    if found:
        print("Saved worlds:", ", ".join(found))
    return ui.ask(
        "World ID (not the module filename)",
        found[0] if len(found) == 1 else "my_world",
        profiles.identifier,
    )


def absolute(value):
    if not value:
        return ""
    if any(c in value for c in '\n\r\0"%\\'):
        raise ValueError(
            "Use a Linux path without control characters, quotes, percent or backslashes"
        )
    return str(Path(value).expanduser().resolve())


def configure(world):
    path = profiles.profile_path(world)
    previous = profiles.load(world) if path.exists() else None
    paths = dict(previous["paths"]) if previous else profiles.defaults()
    found = profiles.discover()
    if found and not previous:
        for index, item in enumerate(found, 1):
            print(
                f"{index}. {item['server_home']} — {item['module'] or 'module not detected'}"
            )
        index = ui.ask(
            "Use detected server number (0 for manual paths)",
            "1" if len(found) == 1 else "0",
            lambda v: (
                int(v)
                if v.isdigit() and 0 <= int(v) <= len(found)
                else ui.invalid("Choose a listed number or 0")
            ),
        )
        if index:
            paths.update({k: v for k, v in found[index - 1].items() if v})
    legacy = profiles.ROOT / ".local/setup-addon.json"
    defaults = dict(
        world_id=world,
        redis_prefix="roleweaver:" + world,
        dashboard_port=8743,
        redis_port=6379,
    )
    if previous:
        defaults.update({k: previous[k] for k in defaults})
    elif legacy.exists():
        old = json.loads(legacy.read_text())
        if old.get("world_id") == world:
            defaults.update({k: old[k] for k in defaults})
            paths["headers"] = old["nwnx_headers"]
            print(
                "Imported this package's old wizard settings; they will now be saved outside the download."
            )
    installed = profiles.installation(world) / "config.json"
    live = json.loads(installed.read_text()) if installed.exists() else None
    if live:
        if live.get("world_id") != world:
            raise ValueError("Installed world identity does not match this folder")
        defaults.update(
            redis_prefix=live["redis_prefix"],
            redis_port=live["redis_port"],
            dashboard_port=live["web_port"],
        )
        print(
            "Existing installation found. Its identity, ports, provider and feature settings will be preserved."
        )
    labels = dict(
        runtime="NWN dedicated server root",
        server_home="This world's server home (userdirectory)",
        module="Module file (.mod; read only)",
        plugins="NWNX plugin folder (contains NWNX_Core.so)",
        headers="Matching NWNX headers folder (contains nwnx_core.nss)",
        compiler="nwnsc executable (enter - to compile in Aurora instead)",
    )
    for key in profiles.PATHS:
        if key == "module" and not paths[key]:
            modules = sorted((Path(paths["server_home"]) / "modules").glob("*.mod"))
            if len(modules) == 1:
                paths[key] = str(modules[0])
            elif modules:
                print("Available modules:", ", ".join(p.name for p in modules))
        answer = ui.ask(labels[key], paths[key] or ("-" if key == "compiler" else ""))
        paths[key] = "" if key == "compiler" and answer == "-" else absolute(answer)
        if not paths[key] and key != "compiler":
            raise ValueError("This path is required: " + labels[key])
    resources = list(previous["resources"]) if previous else []
    override = Path(paths["server_home"]) / "override"
    if override.is_dir() and str(override) not in resources:
        resources.append(str(override))
    print("Resource scan includes:", ", ".join(resources) or "module only")
    print(
        "Add loose script/extracted-HAK folders to inspect. HAK archives are not extracted automatically."
    )
    while True:
        extra = ui.ask("Additional resource folder (blank to continue)")
        if not extra:
            break
        value = absolute(extra)
        if not Path(value).is_dir():
            print("Folder not found:", value)
        elif value not in resources:
            resources.append(value)
    if live:
        redis, port, prefix = (
            defaults["redis_port"],
            defaults["dashboard_port"],
            defaults["redis_prefix"],
        )
    else:
        port = ui.ask("Dashboard TCP port", defaults["dashboard_port"], ui.port)
        redis = ui.ask("Local Redis TCP port", defaults["redis_port"], ui.port)
        prefix = ui.ask("Unique Redis prefix", defaults["redis_prefix"])
    selected = dict.fromkeys(profiles.FEATURES, False)
    selected.update(previous["features"] if previous else {})
    if live and not previous:
        selected.update(
            companions=bool(live.get("companions_enabled")),
            dm_spawn=bool(live.get("allow_dm_spawn")),
            persistent_spawn=bool(live.get("allow_persistent_spawn")),
            guardrails=bool(live.get("guardrails_ai")),
        )
    print(
        "\nBasic AI NPC conversations are always included. Choose additional setup tasks."
    )
    labels = dict(
        companions="Player familiar AI",
        dm_spawn="DM spawning and encounters",
        persistent_spawn="Persist DM-created NPCs across restarts",
        merchants="Merchant/shop integration instructions",
        translation="World text and standard-dialogue translation instructions",
        guardrails="Install the local Guardrails AI dependency",
    )
    for key in profiles.FEATURES:
        selected[key] = (
            ui.yes(labels[key], selected[key])
            if key != "persistent_spawn" or selected["dm_spawn"]
            else False
        )
    p = dict(
        version=1,
        world_id=world,
        redis_prefix=prefix,
        redis_port=redis,
        dashboard_port=port,
        paths=paths,
        resources=resources,
        features=selected,
        progress=previous["progress"] if previous else {},
    )
    profiles.validate(p)
    profiles.installed_settings(p)
    print(
        f"\nWorld: {world}\nModule: {paths['module']}\nDashboard: http://127.0.0.1:{port}/\nSaved profile: {path}"
    )
    if not ui.yes("Save these choices?", True):
        raise ValueError("Configuration cancelled; previous profile is unchanged")
    profiles.save(p)
    return p


def preflight(p):
    rows = profiles.checks(p)
    print("\nCompatibility checklist")
    for row in rows:
        print(f"[{row['status'].upper()}] {row['name']}: {row['detail']}")
    return not any(row["status"] == "fix" for row in rows)


def prepare(p):
    if bundles.current(p):
        output = Path(p["progress"]["bundle"])
        print("Reusing verified preparation:", output)
    else:
        output = bundles.prepare(p)
    print("\nYour server-specific instructions:", output / "INSTALL.md")
    print("Aurora import:", output / "RoleWeaver-Import.erf")
    print("Module/HAK/launcher/plugin files have not been changed.")
    return output


def verify(p):
    if profiles.installed_settings(p) is None:
        print(
            "[WAIT] Role Weaver is not installed for this world. Run setup or install first."
        )
        return False
    manager.own_service(p)
    print(f"\nDashboard: http://127.0.0.1:{p['dashboard_port']}/")
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{p['dashboard_port']}/api/health",
                headers=manager.probe_headers(
                    profiles.installation(p["world_id"]) / "config.json"
                ),
            ),
            timeout=5,
        ) as response:
            data = json.load(response)
    except (OSError, ValueError):
        print(
            f"[WAIT] Dashboard unavailable. Check: systemctl --user status {manager.unit_name(p)}"
        )
        return False
    components = data.get("components", {})
    for key in ("companion", "databases", "redis", "workers", "bridge"):
        item = components.get(key, {})
        print(
            f"[{item.get('state', 'unknown').upper()}] {'Role Weaver service' if key == 'companion' else key}: {item.get('detail', 'No observation')}"
        )
    ok = all(
        components.get(key, {}).get("state") == "healthy"
        for key in ("companion", "databases", "redis", "workers", "bridge")
    )
    if p["features"]["companions"]:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{p['dashboard_port']}/api/companions",
                    headers=manager.probe_headers(
                        profiles.installation(p["world_id"]) / "config.json"
                    ),
                ),
                timeout=5,
            ) as response:
                cp = json.load(response)
            applied = cp.get("status") == "applied" and cp.get("enabled") is True
            print(
                "[OK] Companion AI confirmed by game"
                if applied
                else "[WAIT] Enable companion AI in the dashboard and check its game confirmation."
            )
            ok = ok and applied
        except (OSError, ValueError):
            print(
                "[WAIT] Companion controls are unavailable; check the installed service version."
            )
            ok = False
    if p["features"]["translation"]:
        adapter = components.get("bridge", {}).get("translation_protocol") == 1
        print(
            "[OK] Multiplayer translation adapter observed"
            if adapter
            else "[WAIT] Multiplayer dialogue translation needs the matching adapter and prepared dialogues."
        )
        print(
            "Confirm translation is enabled on the Translations page, then test a reached dialogue in game."
        )
        ok = ok and adapter
    if ok:
        p["progress"]["verified"] = str(int(time.time()))
        profiles.save(p)
        print(
            "Connection checks passed. Next: bind one test NPC and test offline conversation, then select your LLM in the dashboard."
        )
    else:
        p["progress"].pop("verified", None)
        profiles.save(p)
        print(
            "Setup is saved. Finish the generated INSTALL.md, restart NWN with your usual launcher, then run verify again."
        )
    print(
        "Health checks do not replace testing your world's chat filtering, shops, encounters or custom companion systems."
    )
    return ok


def maintenance(p, action):
    if action != "rollback" and not preflight(p):
        raise ValueError(
            "Resolve FIX entries and rerun setup; existing services are unchanged"
        )
    if action == "rollback":
        _, data = manager.rollback_candidate(p)
        print("Restore software:", data["before_release"])
        print(
            "Keeps current player data/configuration. NWN scripts are not rolled back."
        )
    else:
        prepare(p)
        print(
            "The addon uses a persistent Python environment, independent of this downloaded package."
        )
        print(
            "Existing config/keys are retained on update; new feature choices do not overwrite them."
        )
    print(
        f"Target: {manager.unit_name(p)}\nInstallation: {profiles.installation(p['world_id'])}"
    )
    if not ui.yes(
        f"{action.title()} this Role Weaver service? NWN will not be stopped", False
    ):
        print("Deferred; saved setup can be resumed later.")
        return
    if action == "rollback":
        manager.rollback(p)
    else:
        manager.apply(p, update=action == "update")


def translation(p, action):
    if not bundles.current(p):
        prepare(p)
    # Feed saved paths to the existing optional tools without maintaining another
    # settings file. Their output remains a review bundle, not live deployment.
    ui.SAVED_INSTALLATION = p
    try:
        if action == "dialogues":
            ui.dialogues()
        else:
            ui.adapter()
    finally:
        ui.SAVED_INSTALLATION = None


def execute(action="setup", world=None):
    world = choose_world(world, configure=action == "configure")
    p = (
        configure(world)
        if action == "configure" or not profiles.profile_path(world).exists()
        else profiles.load(world)
    )
    print("Saved installation:", profiles.profile_path(world))
    if action == "configure":
        return 0
    if action == "setup":
        if not preflight(p):
            print(
                "Progress saved. Fix the listed prerequisites, then rerun bash setup.sh."
            )
            return 1
        prepare(p)
        installed = profiles.installed_settings(p)
        if not installed:
            maintenance(p, "install")
        else:
            print(
                "Existing addon found. Use update to install this package's software; setup does not silently replace it."
            )
        print(f"\nNext: follow {Path(p['progress']['bundle']) / 'INSTALL.md'}")
        print(f"Resume/check at any time: bash setup.sh verify --world {world}")
        if (profiles.installation(world) / "config.json").exists():
            verify(p)
        return 0
    if action == "check":
        return 0 if preflight(p) else 1
    if action == "prepare":
        prepare(p)
    elif action in ("install", "update", "rollback"):
        maintenance(p, action)
    elif action == "verify":
        return 0 if verify(p) else 1
    elif action in ("dialogues", "adapter"):
        translation(p, action)
    elif action == "status":
        print("Profile:", profiles.profile_path(world))
        print("Progress:", json.dumps(p["progress"], indent=2))
        manager.run(
            ["systemctl", "--user", "status", "--no-pager", manager.unit_name(p)]
        )
    elif action == "restart":
        manager.own_service(p)
        profiles.installed_settings(p)
        if ui.yes(f"Restart only {manager.unit_name(p)}?", False):
            manager.run(["systemctl", "--user", "restart", manager.unit_name(p)])
            verify(p)
    return 0
