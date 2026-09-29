"""Guided Linux setup using the existing, separately callable installation tools.

No API keys are requested. Module, HAK, plugin and launcher changes remain a
reviewed administrator step. Child commands are argv arrays, never shell text.
Local choices are kept outside distribution input folders.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from setup_addon import configuration, required_headers

SETTINGS = ROOT / ".local/setup-addon.json"
PYTHON = ROOT / ".venv/bin/python"
PLUGINS = (
    "Core",
    "Chat",
    "Events",
    "Redis",
    "Creature",
    "Player",
    "Item",
    "Dialog",
    "Util",
)


def ask(label, default="", validator=None):
    while True:
        value = input(
            label + (f" [{default}]" if default != "" else "") + ": "
        ).strip() or str(default)
        try:
            return validator(value) if validator else value
        except (ValueError, OSError) as exc:
            print("Please correct this:", exc)


def yes(label, default=False):
    return (
        ask(
            label + " (y/n)",
            "y" if default else "n",
            lambda s: s.lower() if s.lower() in ("y", "n") else invalid("Enter y or n"),
        )
        == "y"
    )


def invalid(message):
    raise ValueError(message)


def identifier(value):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", value):
        invalid(
            "Start with a lowercase letter; use lowercase letters, digits and underscores, up to 24 characters."
        )
    return value


def port(value):
    if not value.isdigit() or not 1024 <= int(value) <= 65535:
        invalid("Enter a port from 1024 to 65535")
    return int(value)


def path(value):
    if any(c in value for c in ("\n", "\r", "\0")):
        invalid("A path must be on one line")
    result = Path(value).expanduser()
    return (result if result.is_absolute() else ROOT / result).resolve()


def existing(value):
    result = path(value)
    if not result.exists():
        invalid(
            f"Not found: {result}. For new dependencies, open demo/DEPENDENCIES.md or addon/NEW_SERVER.md first."
        )
    return result


def next_output(label):
    for index in range(1, 10000):
        output = ROOT / "builds" / f"{label}-{index:02}"
        if not output.exists():
            return output
    invalid("Too many build folders; choose an output with the advanced tools")


def command(args):
    print("\nRunning:", shlex.join(str(v) for v in args))
    subprocess.run([str(v) for v in args], cwd=ROOT, check=True)


def environment():
    if PYTHON.is_file():
        print("Using the package's .venv Python.")
        ready = (
            subprocess.run(
                [
                    str(PYTHON),
                    "-c",
                    "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('guardrails') else 1)",
                ],
                capture_output=True,
            ).returncode
            == 0
        )
        if ready:
            return
    print(
        "Python dependencies will be installed in this package's .venv folder.\nOn Ubuntu, python3-venv must be installed (sudo apt install python3-venv)."
    )
    if not yes(
        "Create/repair this environment and install Guardrails dependencies now?", True
    ):
        invalid("Environment setup deferred. Run this wizard again when ready.")
    command(["bash", ROOT / "addon/setup.sh", "environment"])


def save_settings(values):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS.with_suffix(".new.json")
    temporary.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    try:
        configuration(temporary)  # Share validation with the existing installer.
        if SETTINGS.exists():
            shutil.copy2(SETTINGS, SETTINGS.with_suffix(".previous.json"))
        os.replace(temporary, SETTINGS)
    finally:
        temporary.unlink(missing_ok=True)


def addon_action(action):
    if not SETTINGS.exists():
        invalid("Choose 'Prepare an existing server' first to save your world settings")
    environment()
    command([PYTHON, ROOT / "tools/setup_addon.py", action, "--config", SETTINGS])


def configure_addon():
    previous = SETTINGS if SETTINGS.exists() else ROOT / "addon/setup.json"
    defaults = json.loads(previous.read_text(encoding="utf-8-sig"))
    print(
        "\nExisting NWN/NWNX server. Your module and HAKs stay where they are.\nNo server is stopped, and no module is edited by preparation."
    )
    world = ask("World ID (not the module filename)", defaults["world_id"], identifier)
    installed = Path.home() / ".local/share/roleweaver" / world / "config.json"
    if installed.exists():
        live = json.loads(installed.read_text())
        defaults.update(
            redis_prefix=live["redis_prefix"],
            dashboard_port=live["web_port"],
            redis_port=live["redis_port"],
        )
        print(
            "This world already has an installation. Its existing ports and Redis prefix are used below."
        )
    else:
        defaults["redis_prefix"] = "roleweaver:" + world
    prefix = ask(
        "Redis prefix",
        defaults["redis_prefix"],
        lambda s: (
            s
            if re.fullmatch(r"[a-zA-Z0-9_:-]{1,80}", s)
            else invalid(
                "Use letters, digits, underscores, colons or hyphens; maximum 80"
            )
        ),
    )
    web = ask("Dashboard TCP port", defaults["dashboard_port"], port)
    redis = ask("Local Redis TCP port", defaults["redis_port"], port)
    if web == redis:
        invalid("Dashboard and Redis must use different ports")
    if installed.exists() and (prefix, web, redis) != (
        live["redis_prefix"],
        live["web_port"],
        live["redis_port"],
    ):
        invalid(
            "This wizard preserves an installed world's settings. Use the existing values; a namespace/port migration needs a coordinated update."
        )
    headers = ask(
        "NWNX headers folder (contains nwnx_core.nss)",
        defaults["nwnx_headers"],
        existing,
    )
    required_headers(headers)
    output = next_output(world + "-import")
    values = dict(
        world_id=world,
        redis_prefix=prefix,
        dashboard_port=web,
        redis_port=redis,
        nwnx_headers=str(headers),
        output=str(output),
    )
    print(
        f"\nWorld: {world}\nRedis prefix: {prefix}\nDashboard: http://127.0.0.1:{web}\nImport bundle: {output}\nSaved settings: {SETTINGS}"
    )
    if not yes("Save these choices and prepare the Aurora import?", True):
        return
    save_settings(values)
    # Preparation is useful on its own, even before Redis/Python setup.
    command(
        [sys.executable, ROOT / "tools/setup_addon.py", "prepare", "--config", SETTINGS]
    )
    print(
        f"\nNEXT: open {output / 'INSTALL.md'}. Import RoleWeaver-Import.erf into a COPY of your module in Aurora; preserve your existing event scripts. The bundled instructions show the exact hooks.\nAfter module preparation, choose 'Install the addon' from this menu. For translation, see docs/TRANSLATION.md."
    )


def native_links(destination, runtime, plugins, headers):
    """Validate everything first; never replace the owner's files or old links."""
    executable = runtime / "bin/linux-x86/nwserver-linux"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        invalid("The NWN runtime must contain executable bin/linux-x86/nwserver-linux")
    if not list((runtime / "data").glob("*.key")) or not list(
        (runtime / "data").glob("*.bif")
    ):
        invalid("The NWN runtime must contain data/*.key and data/*.bif")
    missing = [name for name in PLUGINS if not (plugins / f"NWNX_{name}.so").is_file()]
    if missing:
        invalid("Missing NWNX plugins: " + ", ".join(missing))
    required_headers(headers)
    sources = dict(runtime=runtime, plugins=plugins, nwscripts=headers)
    for name, target in sources.items():
        link = destination / name
        if (link.exists() or link.is_symlink()) and (
            not link.is_symlink() or link.resolve() != target.resolve()
        ):
            invalid(
                f"Existing dependency path differs: {link}. Choose another demo instance; existing links will not be replaced."
            )
    destination.mkdir(parents=True, exist_ok=True)
    for name, target in sources.items():
        link = destination / name
        if not link.is_symlink():
            link.symlink_to(target, target_is_directory=True)


def demo_setup():
    if not (ROOT / "demo/demo.py").is_file():
        invalid(
            "This is the existing-server package. Download the separate demo package to use this option."
        )
    instance = ask("Demo instance name", "rw_demo", identifier)
    settings = ROOT / ".demo" / instance / "settings.json"
    if settings.exists():
        print(
            "This demo is already prepared. Its world, memories and keys will be kept."
        )
        if yes("Start this demo now?", True):
            environment()
            command([PYTHON, ROOT / "demo/demo.py", "start", "--instance", instance])
        return
    print(
        "Enter your existing dependency folders separately; the wizard creates the required links.\nNeed the dependencies first? Open demo/DEPENDENCIES.md, section A."
    )
    runtime = ask("NWN dedicated server folder", "~/nwserver", existing)
    plugins = ask(
        "NWNX plugin folder (contains NWNX_Core.so)", "~/nwnx/plugins", existing
    )
    headers = ask("NWNX headers folder", "~/nwnx/nwscripts", existing)
    compiler = ask("NWScript compiler executable", "~/bin/nwnsc", existing)
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        invalid("The compiler must be executable; use chmod +x on your nwnsc file")
    game = ask("Demo game UDP port", 5125, port)
    web = ask("Demo dashboard TCP port", 8745, port)
    redis = ask("Local Redis TCP port", 6379, port)
    if len({game, web, redis}) != 3:
        invalid("Choose separate game, dashboard and Redis ports")
    destination = ROOT / ".local/native" / instance
    print(
        f"\nDemo data: {ROOT / '.demo' / instance}\nDependency links: {destination}\nGame port: {game} / dashboard: {web}\nThis creates a demo copy; your original world is unchanged."
    )
    if not yes("Prepare this demo now?", True):
        return
    native_links(destination, runtime, plugins, headers)
    environment()
    command(
        [
            PYTHON,
            ROOT / "demo/demo.py",
            "setup",
            "--instance",
            instance,
            "--native",
            destination,
            "--compiler",
            compiler,
            "--game-port",
            game,
            "--web-port",
            web,
            "--redis-port",
            redis,
            "--guardrails",
        ]
    )
    print(
        "\nDemo prepared. Its default DM password is roleweaver. Start prints the game IP/port and dashboard/tunnel instructions. Ctrl+C stops only the demo processes."
    )
    if yes("Start this demo now?", True):
        command([PYTHON, ROOT / "demo/demo.py", "start", "--instance", instance])


def dialogues():
    print(
        "\nOptional: prepare standard NPC dialogues. No LLM calls or cache entries are created.\nUse effective dialogue resources for your world; custom systems and HAK extraction are not automatic."
    )
    module = ask(
        "Your existing .mod file (read only)",
        "~/nwn-world/modules/YourWorld_Fixed.mod",
        existing,
    )
    if not module.is_file() or module.suffix.lower() != ".mod":
        invalid("Choose a .mod file")
    cfg = configuration(SETTINGS) if SETTINGS.exists() else None
    bridge = ask(
        "Prepared bridge source folder (contains rw_settings.nss)",
        str(cfg["output"] / "scripts") if cfg else "builds/my_world-import-01/scripts",
        existing,
    )
    for name in ("rw_settings.nss", "rw_tr_nodes.nss", "rw_tr_native.nss"):
        if not (bridge / name).is_file():
            invalid(f"Missing {name}. Prepare a current bridge first.")
    runtime = ask("NWN dedicated server folder", "~/nwserver", existing)
    headers = ask(
        "NWNX headers folder",
        str(cfg["nwnx_headers"]) if cfg else "~/nwnx/nwscripts",
        existing,
    )
    compiler = ask("NWScript compiler executable", "~/bin/nwnsc", existing)
    resource = ask(
        "One dialogue resource to begin with (blank means all supplied dialogues)"
    )
    if resource and not re.fullmatch(r"[a-z0-9_]{1,16}", resource):
        invalid(
            "Use the dialogue resource name without .dlg, up to 16 lowercase letters, digits or underscores"
        )
    folders = []
    while True:
        extra = ask(
            "Effective loose override/extracted-HAK resource folder (blank to continue)"
        )
        if not extra:
            break
        folders.append(existing(extra))
    token = ask(
        "First reserved custom token (must not overlap your world's existing tokens)",
        3000000,
        lambda s: (
            int(s)
            if s.isdigit() and 100000 <= int(s) < 2147483647
            else invalid("Enter a token number from 100000 to 2147483646")
        ),
    )
    output = next_output("dialogue-translations")
    args = [
        sys.executable,
        ROOT / "tools/prepare_dialogues.py",
        "--module",
        module,
        "--output",
        output,
        "--compiler",
        compiler,
        "--runtime",
        runtime,
        "--includes",
        str(headers) + ";" + str(bridge),
        "--token-base",
        token,
    ]
    if resource:
        args += ["--dialogue", resource]
    for folder in folders:
        args += ["--resources", folder]
    if not yes(f"Prepare the review bundle in {output}?", True):
        return
    command(args)
    print(
        f"\nNEXT: read {output / 'INSTALL.md'}. No running server files were changed. Independent multiplayer dialogue translation also needs the optional native adapter; choose its build option from the main menu."
    )


def adapter():
    print(
        "\nOptional native adapter: currently Linux x86-64 NWN/NWNX 8193.37-17 only.\nUse the matching NWNX source and installed Core binary. A successful build alone does not prove ABI compatibility."
    )
    if (
        ask("Enter the exact supported build to continue (blank cancels)")
        != "8193.37-17"
    ):
        return
    for tool in ("cmake", "c++"):
        if not shutil.which(tool):
            invalid(
                "Build tools are missing. On Ubuntu run: sudo apt install build-essential cmake"
            )
    source = ask("Matching nwnxee/unified source checkout", "~/unified", existing)
    plugins = ask("Installed NWNX plugin folder", "~/nwnx/plugins", existing)
    if (
        not (source / "NWNXLib/nwnx.hpp").is_file()
        or not (plugins / "NWNX_Core.so").is_file()
    ):
        invalid(
            "Choose a source checkout containing NWNXLib/nwnx.hpp and a plugin folder containing NWNX_Core.so"
        )
    output = next_output("translation-adapter")
    if not yes(f"Build a production adapter in {output} (no installation)?", True):
        return
    command(
        [
            "cmake",
            "-S",
            ROOT / "extensions/nwnx_translation",
            "-B",
            output,
            f"-DNWNX_SOURCE={source}",
            f"-DNWNX_CORE={plugins / 'NWNX_Core.so'}",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DRW_TRANSLATION_TESTS=OFF",
        ]
    )
    command(["cmake", "--build", output, "-j2"])
    guide = (
        "# Install the prepared translation adapter\n\n"
        "1. Stop your NWN server for maintenance using its normal launcher/service.\n"
        "2. Back up existing bridge/wrapper scripts, launcher and NWNX_RWTranslation.so.\n"
        "3. Recompile/install current bridge scripts and any existing rtd_*.nss wrappers.\n"
        f"4. Copy `{output / 'NWNX_RWTranslation.so'}` to `{plugins / 'NWNX_RWTranslation.so'}`.\n"
        "5. Add `export NWNX_RWTRANSLATION_SKIP=n` to the NWN launcher before its server command. Keep Dialog, Util, Player and Events enabled.\n"
        "6. Start NWN, then check Health & Support for a fresh heartbeat and translation protocol 1. Enable translation on the Translations page.\n\n"
        "This helper did not edit the launcher or install a plugin. Keep your matching NWN/NWNX build; see extensions/nwnx_translation/README.md for limits and rollback.\n"
    )
    (output / "INSTALL.md").write_text(guide, encoding="utf-8")
    print("\nNEXT: open", output / "INSTALL.md")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if sys.platform != "linux":
        print(
            "Run bash setup.sh inside Ubuntu/Linux. Windows clients can connect to the resulting game server and dashboard."
        )
        return 1
    os.umask(0o077)
    while True:
        print(
            "\nRole Weaver guided setup\n1. Prepare an existing server (world settings and Aurora import)\n2. Prepare or start the separate demo\n3. Check addon prerequisites (saved world)\n4. Install and start the addon (saved world)\n5. Restart the addon only (saved world)\n6. Show addon service status\n7. Prepare existing standard dialogues for translation\n8. Build the optional multiplayer translation adapter\n0. Exit"
        )
        choice = ask("Choose", "0")
        if choice == "0":
            return 0
        try:
            if choice == "1":
                configure_addon()
            elif choice == "2":
                demo_setup()
            elif choice in ("3", "4", "5", "6"):
                action = {"3": "check", "4": "install", "5": "restart", "6": "status"}[
                    choice
                ]
                if action in ("install", "restart"):
                    cfg = configuration(SETTINGS)
                    print(
                        f"Target service: roleweaver-{cfg['world_id']}.service\nData: ~/.local/share/roleweaver/{cfg['world_id']}"
                    )
                    if not yes(
                        f"{action.title()} this Role Weaver Addon service?", False
                    ):
                        continue
                addon_action(action)
            elif choice == "7":
                dialogues()
            elif choice == "8":
                adapter()
            else:
                print("Choose a listed number.")
        except (ValueError, OSError, subprocess.CalledProcessError) as exc:
            print("\nSetup stopped:", exc)
            print(
                "Correct the reported setting/dependency and choose the option again. Existing world data is retained. Advanced guidance: START_ADDON.md, START_DEMO.md and docs/TRANSLATION.md."
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nSetup closed. Saved settings and prepared files are retained.")
