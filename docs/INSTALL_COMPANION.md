# Advanced manual service installation

Most owners should use [START_ADDON.md](../START_ADDON.md) and `bash setup.sh`.
That workflow manages the environment, setup profile, verification and rollback.
This lower-level helper is for custom workflows.

## Install only the Role Weaver service

Use Linux/Python 3.12 and local Redis. From the extracted package:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-guardrails.txt
.venv/bin/python tools/install_companion.py check --world-id my_world --redis-port 6379
.venv/bin/python tools/install_companion.py install --world-id my_world --port 8743 --redis-port 6379 --redis-prefix roleweaver:my_world
```

Replace identity, namespace and ports consistently. The target is
`~/.local/share/roleweaver/my_world`. Read the printed service commands.
This does not install/restart NWN or integrate your module; follow
[the hook reference](../addon/INTEGRATION.md) and [Aurora guide](../addon/AURORA.md).

Retain the Python environment referenced by the generated unit. For a manual
upgrade, stop the selected addon service first; the helper refuses an active
service and creates a verified data recovery point. Prefer guided updates for
versioned environment management and software rollback.

## Service commands

```bash
systemctl --user daemon-reload
systemctl --user start roleweaver-my_world
systemctl --user restart roleweaver-my_world
systemctl --user stop roleweaver-my_world
```

Run the one command you need. These control only Role Weaver; NWN uses its own
launcher/service. To access the dashboard from Windows, keep this tunnel running:

```bash
ssh -N -L 8743:127.0.0.1:8743 USER@SERVER
```

Visit http://127.0.0.1:8743. The initial password is **roleweaver**;
[change it on the server](DASHBOARD_LOGIN.md). Enter provider keys in the dashboard.
Keep Redis and the dashboard private. Back up NWN files separately from
[Role Weaver data](DATABASE_RECOVERY.md). Software rollback does not undo module
edits or restore earlier player databases.
