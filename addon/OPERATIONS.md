# Companion operations

For the current installer, run commands from any extracted package:

```bash
bash setup.sh status --world my_world
bash setup.sh restart --world my_world
bash setup.sh update --world my_world
bash setup.sh rollback --world my_world
```

These reuse `~/.config/roleweaver/installations/my_world.json`. Updates preserve
configuration/data and verify service startup; rollback restores managed software
without rewinding player data. NWN/module deployment stays in your normal workflow.
See [guided setup](../docs/GUIDED_SETUP.md) for recovery and older installations.

The remaining commands are the **legacy/manual interface**, reading addon/setup.json.
The older wizard file can be selected explicitly with `--config .local/setup-addon.json`.
Do not mix this interface with the new saved-profile workflow unintentionally.

## Restart the dashboard/AI companion

```bash
bash addon/setup.sh restart
bash addon/setup.sh status
```

This does not restart NWN or disconnect players. NWScript/module changes require a separate game restart through your existing server controls.

## Updating

Keep backups of the companion data, native campaign databases, and your current module. Extract the new package into a permanent folder and copy your previous addon/setup.json into it. The existing service's Python environment must remain available until replacement succeeds.

Run `bash addon/setup.sh environment` and `bash addon/setup.sh check`. Stop the companion you intend to update, using your actual world ID:

```bash
systemctl --user stop roleweaver-my_world.service
bash addon/setup.sh install
```

The installer preserves its config/data and starts the updated companion. Do not stop an unrelated world to reuse its ID. Prepare a new numbered import folder only if bridge scripts changed; review resource replacements and schedule the separate module update.

## Dashboard from Windows

On Ubuntu, run `hostname -I` to find the VM's IP. In a Windows terminal, substitute your username/IP and configured dashboard port:

```powershell
ssh -N -L 8743:127.0.0.1:8743 USER@UBUNTU-IP
```

Leave that terminal open, then browse to http://127.0.0.1:8743. Use the same local
and remote dashboard port: the dashboard validates the browser's Host header.
If 8743 is busy, close the old tunnel or choose another `web_port` in the installed
world's config, restart that Role Weaver service and use the new port in all three
places. Keep Redis and the dashboard on loopback. The dashboard is an administrator
interface without individual logins; see [security and resource limits](../docs/SECURITY_AND_LIMITS.md).

## Common problems

| Message or symptom | What to check |
| --- | --- |
| Missing NWNX script | nwnx_headers must point to the folder containing the matching NWScript.zip contents, not the `.so` folder. |
| Output directory already exists | Change output in addon/setup.json from `-01` to `-02`. Existing bundles are preserved. |
| Address already in use | Use status/restart for the existing companion, or choose a distinct dashboard port/world ID for a separate world. |
| Game connects but dashboard waits for NPCs | Confirm NWNX loaded, correct module events, same world ID/Redis prefix/port, and a bound NPC. |
| No Spawn at DM | Enable both module flags and companion config options, restart the game after module changes, and connect as DM. |
| Offline responses | Choose a provider in LLM Settings and run its connection test. |
| Guardrails unavailable | Run environment with this package's helper, then check requirements-guardrails.txt installation output. The local adapter uses guardrails_ai in installed config; provider-backed review is a separate dashboard setting. |

To inspect companion errors, run `journalctl --user -u roleweaver-my_world.service -n 50 --no-pager`, using your world ID. Keep logs private; they may contain dialogue. Do not send API keys or provider.env with bug reports.
