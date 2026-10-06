# Install Role Weaver alongside your existing NWN server

Use the **Server Add-on** package on the Linux account that owns your NWN/NWNX
server. Your module, HAKs, plugins and launcher stay in their current folders.
The Demo is a separate package.

## 1. Open the extracted package folder

Open a terminal in the extracted folder and run, **without sudo**:

```bash
bash setup.sh gui
```

The graphical installer prints an SSH tunnel command and a private browser URL.
Run the tunnel on your Windows computer, open the URL, and follow the six setup
pages. The setup page listens only on the Linux server's loopback interface.

On a private, single-user server you can avoid copying the temporary access token:

```bash
bash setup.sh gui --trusted-local
```

After opening the printed SSH tunnel, browse directly to `http://127.0.0.1:8750/`.
Anyone with local access to that Linux host can use setup while this mode is running,
so close it with Ctrl+C when finished. Use the normal token mode on shared hosts.

If you prefer the terminal workflow, run `bash setup.sh` and choose
**1 — Set up / resume an existing server**. Both interfaces use the same saved
profiles, checks, bridge builder, service installer and rollback system.

If you need to install NWN/NWNX first, follow [New server setup](addon/NEW_SERVER.md).
On a fresh Ubuntu host you may also need `sudo apt install python3-venv redis-server`.
Do not change an established server's Redis configuration without checking its other users.

## 2. Tell setup which server to use

The graphical and terminal installers suggest paths from a running NWN process or common installation folders.
Check each suggestion, particularly if you run several worlds. Select:

- A short **world ID**, such as `my_world`. This is not the module filename.
- Your NWN runtime, server home/userdirectory, module, NWNX plugin and matching header folders.
- An installed `nwnsc` compiler, or `-` to compile the import in Aurora instead.
- Features you want to prepare, plus unused dashboard and local Redis ports.

Each server path has a **Browse** button. It opens the Ubuntu filesystem, not the
Windows computer, and filters module and compiler selections appropriately.

Setup saves these choices outside the download, in
`~/.config/roleweaver/installations/my_world.json`. It can reuse them from a later
package. API keys are entered in the dashboard, not the installer.

## 3. Follow the compatibility checklist

**FIX** means a prerequisite needs attention. **REVIEW** means a server-specific
integration choice needs your judgement. Correct missing dependencies and rerun
`bash setup.sh`; your choices are kept. File checks do not prove that plugin
versions match or that the running server loaded them.

Setup generates one folder containing **INSTALL.md**, **RoleWeaver-Import.erf**,
source scripts, optional compiled scripts and a resource review. Its instructions
use your actual paths and selected settings. Preparation does not edit your module.

## 4. Install the Role Weaver service

The same flow offers to install it. It creates a persistent Python environment,
installs the optional Guardrails dependency if selected, and starts the addon.
NWN is not stopped or restarted. Existing installations use the separate update command below.

Open the dashboard address printed by setup. For Windows access use the SSH tunnel
command in the generated INSTALL.md. Keep the dashboard and Redis private on loopback.

The initial dashboard password is **roleweaver**. See [Dashboard login](docs/DASHBOARD_LOGIN.md)
to change it from the server terminal. Existing installations retain their chosen password.

## 5. Connect your module

Open the **generated INSTALL.md**, which shows your existing event assignments.
Use its Aurora import or your server's normal script-build workflow.

Keep existing scripts. Role Weaver needs a call from your module initialization
and **one** approved public-chat route after filtering/moderation. For a modified
world, the script maintainer must choose that chat integration point. Setup does
not guess where private or rejected messages should be forwarded.

The guide covers selected feature flags, blueprints, required plugins and optional
translation preparation. New/empty modules can use the supplied event templates.
Custom modules need the small hook calls added to their existing handlers.

Back up the original module, compile your changes, deploy them through your normal
process and restart **that NWN instance** during your maintenance window.

## 6. Verify and try one NPC

```bash
bash setup.sh verify --world my_world
```

This checks the service, databases, Redis and actual game heartbeat. It also checks
companion confirmation and the multiplayer translation adapter when selected.
NPC binding, merchant compatibility and custom game behavior still need a playtest.
Start with offline NPC conversation, then choose your provider in **LLM Settings**.

## Updating later

Extract the new package and run:

```bash
bash setup.sh update --world my_world
```

It reuses your saved profile, prepares changed bridge files for review, builds the
new Python environment before stopping the addon, creates a verified database
recovery point, updates the addon and checks startup. It preserves existing config,
keys and data. New feature selections do not overwrite installed settings.

Review the new generated INSTALL.md for game-script changes. Deploy those separately
with your normal NWN maintenance process. The installer never restarts NWN.

To revert an update made by this installer:

```bash
bash setup.sh rollback --world my_world
```

This restores the previous software and its Python environment while keeping current
configuration and player data. It does not undo module/plugin changes or restore old
memories. Database restoration remains in **Database & Recovery**.

[Setup commands, migration and troubleshooting](docs/GUIDED_SETUP.md) ·
[Custom-world integration](addon/INTEGRATION.md) · [Aurora details](addon/AURORA.md)
