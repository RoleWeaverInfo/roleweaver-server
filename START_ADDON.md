# Role Weaver Server Add-on — alpha 0.1.0

For an existing Linux NWN:EE server with NWNX:EE. This download contains no demo world.
Your module stays where it is. Role Weaver runs as a separate companion and never starts or
restarts NWN. Test on staging before production.

## 1. Prepare Python

Extract to a permanent folder separate from the server. Open a terminal there:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-guardrails.txt
```

Ubuntu 24.04/Python 3.12 is the tested baseline. Keep this environment available: the generated
service uses it. Install your distribution's python3-venv package if necessary.

## 2. Check prerequisites and choose a world identity

The examples use `my_world`, Redis prefix `roleweaver:my_world`, and dashboard port `8743`.
Use the same values throughout. The world ID is a namespace, not a module filename or area tag.

Required NWNX plugins: Core, Chat, Events, Redis, Creature and Player, with matching headers and
a compatible dedicated server build. Preserve your existing launcher/plugin configuration.
Do not set NWNX_CORE_SKIP_ALL: it could disable your other plugins.

The Python bridge currently supports unauthenticated Redis on localhost with a configurable port.
Do not weaken an existing authenticated/remote Redis service. Review
[compatibility notes](addon/COMPATIBILITY.md) if your setup differs, especially if other systems
already use NWNX Redis.

```bash
python tools/install_companion.py check --world-id my_world --redis-port 6379
```

Resolve errors first. This check cannot prove native plugin compatibility.

## 3. Install the companion only

```bash
python tools/install_companion.py install --world-id my_world --port 8743 --redis-port 6379 --redis-prefix roleweaver:my_world
```

Default target: `~/.local/share/roleweaver/my_world/`. Existing configuration is preserved on upgrades.
Run the exact service commands printed by the installer. They start Role Weaver, not NWN.

Open http://127.0.0.1:8743 on the server. For remote access, run this on your computer:

```bash
ssh -N -L 8743:127.0.0.1:8743 USER@SERVER
```

Then open the same URL locally. Keep the dashboard and Redis private. Leave the provider offline
until game integration works. A disconnected bridge is expected at this stage.

To enable the optional local Guardrails AI adapter, set `"guardrails_ai": true` in the installed
config.json and restart only the companion. Its Python environment must have the requirements from
Step 1 installed. Provider-backed policy reviews are configured separately in the dashboard.

## 4. Prepare bridge files without touching your module

Choose one build method. Replace the example paths with existing locations on your server:

```bash
python tools/prepare_addon.py \
  --world-id my_world \
  --redis-prefix roleweaver:my_world \
  --runtime /YOUR/EXISTING/NWN/RUNTIME \
  --includes /YOUR/EXISTING/NWNX/HEADERS \
  --compiler /YOUR/EXISTING/nwnsc \
  --output builds/my_world-bridge-01
```

Runtime means the folder containing NWN data/*.key and data/*.bif. Includes means the folder of
matching nwnx_*.nss headers. These inputs are read in place; no special folder layout or module copy
is required inside Role Weaver.

Alternatively, prepare source for your world's normal build pipeline:

```bash
python tools/prepare_addon.py --world-id my_world --redis-prefix roleweaver:my_world --source-only --output builds/my_world-bridge-01
```

Compile scripts/ with your existing toolchain. Choose a new output directory for subsequent builds.

## 5. Integrate into the existing world

Open **builds/my_world-bridge-01/INSTALL.md**. Follow its instructions to:

1. Call rw_init after your existing module initialization.
2. Add exactly one chat adapter after your own moderation/privacy decisions.
3. Bind one existing test NPC, leaving your spawn system in charge.

Install compiled resources through your normal module/override workflow. Compile your modified
existing handlers and restart the staging NWN server through your usual maintenance procedure.
The preparer does not install game files or replace event handlers. Check rw_* resource collisions
across module, HAKs and override folders before installation.

## 6. Verify and test one NPC

```bash
python tools/check_addon.py --port 8743
```

Dashboard, Redis, conversation bridge and action protocol should report OK after initialization.
Zero NPCs is normal before binding. Create the profile ID used in your binding hook, resume it in
the dashboard, and talk as a player. New bindings start paused.

After offline conversation and DM takeover work, configure an LLM in the dashboard. Follow
[acceptance tests](addon/ACCEPTANCE_TESTS.md) before production use. The checker makes no LLM request.

## Stop, restart and rollback

```bash
systemctl --user stop roleweaver-my_world
systemctl --user restart roleweaver-my_world
```

These affect only the companion. See [rollback](addon/ROLLBACK.md) for game-hook removal.
The demo is a different download; never run its setup against an established world.
