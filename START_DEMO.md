# Role Weaver editable demo — alpha 0.1.0

This package runs a separate demo NWN server and Role Weaver dashboard on Linux. Ubuntu 24.04
(or an Ubuntu VM on Windows) is the tested target. No Docker is required. It starts in offline mode;
choose an LLM in the dashboard when ready. It does not use an existing world's data or API keys.

## 1. Prepare dependencies once

You need Python 3.12, Redis, an NWN:EE client to play, and a compatible Linux **dedicated server**,
NWNX:EE plugins/headers, and the `nwnsc` compiler. The game runtime and NWNX binaries are not
bundled. **First follow [the step-by-step dependency guide](demo/DEPENDENCIES.md):**

- **New installation:** section A downloads/installs the dedicated server, matching NWNX plugins/headers, Redis and compiler. Then section C creates the folder links.
- **Already installed:** section B identifies your existing folders, and section C links them into the layout the demo expects. You do not need to move or reinstall them.

Section D returns you to this package folder and runs setup. If you finish that section, continue here at **Step 4**. Otherwise continue below once dependency checks pass.

## 2. Open a terminal in the extracted package

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-guardrails.txt
```

Use that same activated environment whenever starting the demo.

## 3. Build your demo

The dependency guide creates `~/nwn-demo-deps` containing links named `runtime`, `plugins` and `nwscripts`. **Do not point --native directly at ~/nwserver or ~/nwnx.** Keep the command below if you followed the standard layout; change only --compiler if your compiler lives elsewhere:

```bash
.venv/bin/python demo/demo.py setup --native "$HOME/nwn-demo-deps" --compiler "$HOME/bin/nwnsc" --guardrails
```

This prepares `.demo/rw_demo/`. It compiles a **copy** of `demo/world/YourWorld_Fixed.mod`, adds the demo
NPCs and creates fresh data. It does not change the source world. If a required file is missing, setup
stops and names it. Setup does not start anything. Re-running setup never overwrites a prepared instance.

## 4. Start

```bash
.venv/bin/python demo/demo.py start
```

The startup output lists the detected Ubuntu/VM game IP addresses, game port, local dashboard URL, and an SSH tunnel command for Windows. With multiple network interfaces, choose the Ubuntu address reachable from your client.

Keep the terminal open. Wait for NWN to finish loading, then open the dashboard at
**http://127.0.0.1:8745**. In NWN Direct Connect use **127.0.0.1:5125** if the client is on the same Linux
machine. From Windows to a VM, use **VM-IP:5125**. Use `hostname -I` in Ubuntu to find its IP.
The demo is unlisted and accepts local characters; a player password is not set. The generated DM
password is stored in `.demo/rw_demo/settings.json` (keep this file private).

To open the VM dashboard from Windows, leave this SSH tunnel running, substituting your VM user/IP:

```bash
ssh -N -L 8745:127.0.0.1:8745 USER@VM-IP
```

Then open http://127.0.0.1:8745 in Windows. If a firewall is enabled, allow UDP 5125 only from your
trusted client/network. Keep Redis and the dashboard private.

## 5. Meet the NPCs

Explore Crown Hall in the Kingdom of Role Weaver. Meet **Captain Beran**, **Kevin** the innkeeper, the **Merchant**, **Aldren** the wizard, **Sister Meriel**, and **Quartermaster Holt**. Ask the guard about your investigation and an audience with the King. Read or examine the noticeboard for activities.
Right-click an NPC and choose Talk To/Speak, or address them by name to begin. Stay close.
They should appear in the dashboard and start in auto mode. Offline replies are explicitly marked.

In **LLM Settings**, enter your provider/model and key, run the connection test, then save. LM Studio
can be used instead of a cloud key. Models/quotas and inference speed depend on the provider or host.

The Merchant's shop starts with a small weapon selection. Ask to see the stock or haggle.
Ask NPCs to lead you to the visitor table, merchant stall, wizard study, shrine or royal dais.
Collect witness accounts about the caravan attack, then present your conclusion to the King.
The investigation resets each login; NPC memories of previous conversations remain.

## 6. Stop or return later

Press **Ctrl+C in the demo terminal**. This stops only the two processes started by this launcher.
Later, open a terminal in the package folder and run `.venv/bin/python demo/demo.py start` again. Profiles, memories, keys and game
campaign data stay in `.demo/rw_demo/`. This is a foreground demo runner, not a production service.

## Optional testing and customization

- [Quick playtest](demo/PLAYTEST.md)
- [Guardrails and model comparison](demo/LLM_COMPARISON.md)
- [Edit the world, NPCs and lore](demo/CUSTOMIZE.md)
- [Report a problem](demo/REPORTING.md)

If startup fails, read `.demo/rw_demo/game.log`, `dashboard.log` and `nwnx.log`. Never publish those
files wholesale: they can contain player dialogue or local details. Logs are local troubleshooting
files; automated redacted diagnostic export remains a separate planned feature.

## If every message is blocked

If Guardrails reports **unavailable**, this is an installation/environment problem, not a sensitivity setting. Start with `.venv/bin/python demo/demo.py start` so the launcher uses the environment where you installed Guardrails. Do not rebuild or delete your demo data. If needed, repair that environment with `.venv/bin/python -m pip install -r requirements-guardrails.txt`.
