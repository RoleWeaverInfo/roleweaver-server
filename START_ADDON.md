# Role Weaver Server Add-on — start here

This package adds Role Weaver to an NWN:EE/NWNX Linux server. Your module stays in your server's `modules` folder. The demo is a separate download.

**Choose your starting point:**

- **My NWN/NWNX server already works:** follow steps 1–6 below.
- **I need to create a server first:** follow [New server setup](addon/NEW_SERVER.md), then return here.
- **I only want to play the supplied investigation:** use the Demo download and its START_HERE.md. The optional YourWorld_Fixed example is already hooked; do not import the generic bridge over it.

## 1. Extract the add-on and open its folder

Extract `RoleWeaver-Server-Addon-Alpha-0.1.0.tar.gz` on Ubuntu. Open the extracted folder in Files, right-click empty space and choose **Open in Terminal**. All commands below run in this folder. Keep the folder after installing.

Your existing server, module, HAKs and launcher stay where they are.

## 2. Edit one settings file

Open **addon/setup.json** in a text editor. Save it after editing:

| Field | What to enter |
| --- | --- |
| `world_id` | A short identifier, such as `my_world`. Lowercase letters, digits and underscores; start with a letter. This is NOT the module filename. |
| `redis_prefix` | A unique prefix, such as `roleweaver:my_world`. Use the same value for this world's bridge and companion. |
| `dashboard_port` | An unused TCP port; example `8743`. |
| `redis_port` | The local Redis port; normally `6379`. |
| `nwnx_headers` | The Ubuntu folder containing `nwnx_core.nss`, from the NWScript.zip matching your installed NWNX build. Example `~/nwnx/nwscripts`. |
| `output` | A new folder for the import files. Leave `builds/my_world-import-01` for your first build; use `-02` for another. |

Keep JSON double quotes and commas. Do not put API keys or passwords in this file.

## 3. Prepare Python and check Redis

For a fresh Ubuntu installation, first run:

```bash
sudo apt install python3-venv redis-server
```

Ensure your local Redis service is running. Then run these two commands, one at a time:

```bash
bash addon/setup.sh environment
bash addon/setup.sh check
```

The first creates the Python environment and installs dependencies. The second checks the companion prerequisites. Each later command uses that environment automatically. Redis must be local and compatible with the [transport requirements](addon/COMPATIBILITY.md); keep an established server's Redis configuration intact.

## 4. Create the Aurora import file

```bash
bash addon/setup.sh prepare
```

It prints the path to **RoleWeaver-Import.erf** and **INSTALL.md**. This step does not change or stop your server.

The ERF contains the Role Weaver script sources, creature/store blueprints, two editable event templates, and all required NWNX headers including their dependencies. It uses YOUR matching NWNX headers, so you do not need to find and copy individual include files.

Follow [Edit your module in Aurora](addon/AURORA.md). That guide explains importing, compiling, assigning events, preserving existing scripts, and copying the finished module back to Linux.

## 5. Install the companion

```bash
bash addon/setup.sh install
```

This installs and starts the Role Weaver companion, not NWN. It preserves existing configuration and data. If the installer reports an active existing installation, see [Updating](addon/OPERATIONS.md) instead of stopping a service belonging to another world.

Open **http://127.0.0.1:8743** in Ubuntu (use your configured dashboard port). For Windows access, see [Dashboard access](addon/OPERATIONS.md#dashboard-from-windows).

If you enabled DM spawning in the module, also enable `allow_dm_spawn` and optionally `allow_persistent_spawn` in the installed config. [The Aurora guide](addon/AURORA.md#optional-dm-spawning) shows both sides.

## 6. Start the edited game module and test

Start NWN with your existing launcher and the edited module. Check its log: **Core, Chat, Events, Redis, Creature and Player** must load. `NWNX_CHAT_SKIP=n` means Chat is enabled. A working game connection alone does not prove NWNX loaded.

In the dashboard, create a profile with stable ID `test_guard`. Log in as DM, stand near a creature and say `!rw bind test_guard CREATURE_TAG`, replacing CREATURE_TAG with that creature's actual Tag from Aurora. Select Resume in the dashboard. Reconnect as a player and use Talk To near it. You should receive an offline test response. Configure your provider in LLM Settings when the bridge works.

For permanent world-owned NPCs, use your world's normal spawn/load path as described in [advanced integration](addon/INTEGRATION.md). A one-time DM binding does not modify the saved module.

## Keep these guides handy

- [Aurora: import, event scripts, compile and deploy](addon/AURORA.md)
- [Restart, update, dashboard access and troubleshooting](addon/OPERATIONS.md)
- [Established-world integration details](addon/INTEGRATION.md)
- [Playtest checklist](addon/ACCEPTANCE_TESTS.md)
- [Rollback](addon/ROLLBACK.md)
