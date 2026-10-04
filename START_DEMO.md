# Start the Role Weaver demo

The demo is a separate editable NWN world: Crown Hall, a forest robbery, a troll
hostage scene in a cave, an investigation, shops and a Royal Guide.
Use Ubuntu 24.04 x86-64. Your NWN:EE game client can remain on Windows.

## 1. Prepare the dependencies

You need the Linux **dedicated server**, matching **NWNX plugins and headers**,
**Redis**, **Python 3.12** and **nwnsc**. They are not in this download.

- **Nothing installed:** follow **A1–A4** in [DEPENDENCIES.md](demo/DEPENDENCIES.md).
- **Already installed:** use its **B** folder-identification table. Keep your folders.

The wizard below links those folders for you. Manual steps C/D in that guide are
an alternative, not extra requirements for wizard users.

## 2. Run setup

Extract the download and open an Ubuntu terminal **inside the package folder**:

```bash
bash setup.sh
```

Choose **2 — Demo**. Use `rw_demo` as the instance name for a first test.
Supply the actual dedicated-server root, NWNX plugin/header folders and compiler.
Common paths are `~/nwserver`, `~/nwnx/plugins`, `~/nwnx/nwscripts` and `~/bin/nwnsc`.

The wizard prepares Python and a copy of the source module in `.demo/rw_demo/`.
Existing instances are preserved. Select Guardrails if wanted; provider-backed
review is configured separately in the dashboard.

## 3. Start or stop

Choose Start when offered. To start again later, from the package folder:

```bash
.venv/bin/python demo/demo.py start
```

Keep this terminal open. **Ctrl+C** stops the game and addon owned by this launcher.
For another instance name, add `--instance YOUR_NAME`.

## 4. Connect

**Use the addresses and ports printed at startup.** Defaults:

| Connection | On Ubuntu | From another computer |
| --- | --- | --- |
| NWN Direct Connect | `127.0.0.1:5125` | `UBUNTU-IP:5125` |
| Dashboard | `http://127.0.0.1:8745` | Same URL through the SSH tunnel below |

From Windows, leave this tunnel running, replacing USER and VM-IP:

```bash
ssh -N -L 8745:127.0.0.1:8745 USER@VM-IP
```

The initial **dashboard password is `roleweaver`**.
For a DM connection, launch NWN:EE in **DM client mode** (`-dmc`), connect to the
same **game** port, and enter the separate **DM password `roleweaver`**.
Ordinary player connections have no password by default. Change both known defaults
before sharing a demo; keep the dashboard private. See [Dashboard login](docs/DASHBOARD_LOGIN.md).

If an older demo's DM password is unknown, stop it, run
`.venv/bin/python demo/demo.py reset-dm-password`, then restart.
To choose a private DM password instead, edit `dm_password` in
`.demo/rw_demo/settings.json` while stopped.

## 5. Configure AI and play

In **LLM Settings**, select your provider/model, enter a key or local endpoint,
test and save. Until configured, responses use offline mode.
Companion AI is enabled by default in new demos. Summon a familiar normally, then
use `/rw companion on` in Talk to activate its AI. Administrators can manage the
service in the dashboard's **Companions** panel.

The **Translations** service is also enabled by default in new demos; each player
chooses a language and turns translation on through `/rw language` in Talk.
Text is translated on demand using
the configured provider, then cached for reuse. Existing demos keep their saved
setting, which can be changed in the dashboard's **Translations** panel.

Talk to the **Royal Guide** at the entrance for a walkthrough.
Ask **Captain Beran** about the investigation. Meet the Tavern Owner, Merchant,
wizard, cleric and Holt. Doors lead to the forest robbery and cave hostage scenes.
Use Talk To/Speak or address an NPC by name, then continue nearby Talk.

- [Activities and familiar walkthrough](demo/PLAYTEST.md)
- [Forest and cave encounters](demo/ENCOUNTER_AREAS.md)
- [Edit the world, characters, lore and HAKs](demo/CUSTOMIZE.md)
- [Troubleshooting and reports](demo/REPORTING.md)
- [Optional administrator model evaluation](demo/LLM_COMPARISON.md)

New instances start with authored content, empty memories and an empty translation
cache. Later conversations and translations persist between starts. Retain/back up
`.demo/rw_demo/` to keep custom changes; never include that private folder in a download.

For missing files, use [dependency checks](demo/DEPENDENCIES.md).
If Guardrails is unavailable, use the package's `.venv/bin/python`; repair it with
`.venv/bin/python -m pip install -r requirements-guardrails.txt`.
Prefer **Health & Support → Download support report** over raw logs.
