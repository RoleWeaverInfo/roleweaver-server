> **Existing-server installation:** start with [START_ADDON.md](../START_ADDON.md) and its manual bridge hooks. Module-copy examples below are optional advanced workflows, not required for the existing-server distribution.

# Companion installation reference

This source milestone is for developers. A guided server-owner package is planned; see the
[alpha checklist](ALPHA_CHECKLIST.md). The current helper installs the Python companion only.
It does not install NWN/NWNX, patch your running world, or automatically activate the systemd unit.

## Prerequisites

Linux/Python 3.12, a compatible existing NWN:EE/NWNX installation, and local Redis. Use an isolated
staging world and back up its module, scripts and campaign data. Install optional Guardrails into the
same Python environment used to invoke the helper if you need AI validation.

## Check and install a staging companion

From the repository root, with your development virtual environment active:

```bash
python tools/install_companion.py check --world-id my_world
python tools/install_companion.py install --world-id my_world --port 8743
```

The default target is `~/.local/share/roleweaver/my_world`. Read the printed service commands and
configuration path before starting it. Set the world's Redis port/prefix consistently using the helper
arguments (`--help` lists them). Keep the environment used by the generated service available.

## Connect the game

Follow [INTEGRATION.md](INTEGRATION.md) to build and review a bundle against a copy of your world.
Install during a staging maintenance window using the bundle's generated INSTALL.md and manifest.
Preserve existing load/chat handlers. Installing the companion alone cannot make an NPC speak.

## Remote dashboard

Run this on your own computer, substituting your SSH user and server hostname:

```bash
ssh -N -L 8743:127.0.0.1:8743 USER@SERVER
```

Open http://127.0.0.1:8743. Keep the dashboard and Redis private. Configure providers in the dashboard;
never put credentials into the source checkout. Validate player conversation, DM takeover and restart
behavior before using the integration on a production world.

## Rollback

Retain the previous companion release/configuration and a backup of application data. Use the generated
bundle manifest to reverse only the installed game changes, restore original event handlers and restart
the staging world. Preserve database backups; consult [BACKUP_RESTORE.md](BACKUP_RESTORE.md).
