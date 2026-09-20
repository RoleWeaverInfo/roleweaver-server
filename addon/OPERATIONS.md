# Companion operations

Run commands from the extracted package folder. They read addon/setup.json.

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

Leave that terminal open, then browse to http://127.0.0.1:8743. If local port 8743 is busy, use `-L 8744:127.0.0.1:8743` and open http://127.0.0.1:8744. The middle port is always the Ubuntu dashboard port. Keep Redis and the dashboard on loopback.

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
