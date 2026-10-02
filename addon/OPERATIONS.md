# Run and maintain Role Weaver

Use your saved world ID instead of `my_world`. Run commands from an extracted package:

| Task | Command |
| --- | --- |
| Check status | `bash setup.sh status --world my_world` |
| Restart Role Weaver | `bash setup.sh restart --world my_world` |
| Update software | `bash setup.sh update --world my_world` |
| Roll back a managed update | `bash setup.sh rollback --world my_world` |
| Check the game connection | `bash setup.sh verify --world my_world` |

To stop only Role Weaver: `systemctl --user stop roleweaver-my_world`.
To start it: `systemctl --user start roleweaver-my_world`.

These commands do not restart NWN. Use your world's game launcher/service when
deploying changed scripts or plugins. The demo has its own foreground runner;
follow its START_HERE.md instead.

## Updates

Extract the new download. Guided setup reuses
`~/.config/roleweaver/installations/my_world.json`, prepares dependencies, takes
a verified recovery snapshot and checks startup after updating. It retains config,
passwords, provider keys and player data. Keep earlier releases/environments for
rollback. Review the generated INSTALL.md for separate game-script changes.
See [guided setup](../docs/GUIDED_SETUP.md) for migration from legacy installations.

## Dashboard from Windows

Open a Windows terminal and keep this tunnel running:

```powershell
ssh -N -L 8743:127.0.0.1:8743 USER@UBUNTU-IP
```

Use the port selected for this world in all three places. Browse to
http://127.0.0.1:8743. The initial password is **roleweaver**;
[change/reset it from the server](../docs/DASHBOARD_LOGIN.md).
Keep the dashboard and Redis on loopback.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing NWNX include | Headers must match the installed plugins; plugins alone are insufficient. |
| Address already in use | Restart the existing service instead of starting a second copy; separate worlds need separate dashboard ports. |
| Game works but bridge is offline | Check loaded NWNX plugins, hooks, matching world/Redis settings and the Health panel. |
| No Spawn at DM | Enable corresponding module and service settings, load the updated scripts and connect as DM. |
| Offline replies | Choose and test a provider in LLM Settings. |
| Guardrails unavailable | Repair the Python environment selected by setup; inspect Health and Guardrails. Provider-backed reviews are a separate setting. |
| Data appears missing after reinstall | Check the world ID and installation folder before importing anything. |

Inspect local logs with `journalctl --user -u roleweaver-my_world.service -n 50 --no-pager`.
Prefer a filtered Health & Support report when requesting help. Raw logs and database
backups may contain private data. Legacy low-level commands are documented in
[manual installation](../docs/INSTALL_COMPANION.md); do not mix workflows accidentally.
