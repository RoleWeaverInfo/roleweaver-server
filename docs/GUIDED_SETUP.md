# Guided installation and maintenance

From the extracted package run `bash setup.sh gui`, without sudo, as the Linux
server owner. It prints a localhost URL and, for remote administration, the exact
SSH tunnel command to run on Windows. The browser wizard covers server discovery,
configuration, checks, preparation, install/update and verification. It binds only
to `127.0.0.1`, uses a new random access token each time and stores no SSH credentials.

The terminal workflow remains available through `bash setup.sh`. Choose **1** for
continuous existing-server setup or **2** for the separate Demo. Both interfaces
use the same profiles and installation backend.

## Windows remote installer

The optional Windows application uses the installed Windows OpenSSH client. It
streams a selected Server Add-on archive through one authenticated SSH connection,
starts the Linux GUI, maintains its loopback tunnel and opens the browser. The
archive is not copied into a permanent upload folder. Its temporary extraction is
removed when the connection closes; installed services and saved profiles remain.

SSH passwords and key passphrases are held in process memory only. Normal
`known_hosts` verification remains active: an unseen host can be accepted once,
while a changed host key is rejected. The application never asks for a Linux root
password and does not expose the setup port publicly. Advanced administrators can
continue to run the Linux and terminal installers directly.

## One saved profile per world

Existing-server choices and progress are saved in
`~/.config/roleweaver/installations/WORLD.json`, readable only by the owner.
They contain paths, ports, feature choices and output locations, never API keys.
Reopen setup from any later extracted package to resume. Use `--world` when you
have more than one world. Reconfigure to correct paths after moving a module.

The application still owns its runtime configuration, credentials, databases and
backups under `~/.local/share/roleweaver/WORLD/`. Those files are independent of
the installation profile. A saved feature choice describes what to prepare; it
is not proof that the native hook, plugin or dashboard permission is active.

The dashboard initially asks for **roleweaver**. Set your own password from the
server terminal using [Dashboard login](DASHBOARD_LOGIN.md). Updates retain it;
installer health checks use a separate, read-only local credential.

## Commands

Run these from an extracted package; replace `my_world` with your saved ID.

| Command | Purpose |
| --- | --- |
| `bash setup.sh gui` | Start the localhost graphical installer on port 8750. |
| `bash setup.sh gui --trusted-local` | Open directly through a private tunnel without copying a token; use only on a trusted single-user host. |
| `bash setup.sh gui --port 8751` | Use another local setup port. |
| `bash setup.sh setup --world my_world` | Resume checks, bridge preparation, initial install and connection guidance. |
| `bash setup.sh configure --world my_world` | Edit paths and feature choices. Existing runtime identity/ports are preserved. |
| `bash setup.sh check --world my_world` | Read-only prerequisites and actionable corrections. |
| `bash setup.sh prepare --world my_world` | Produce/reuse a verified integration bundle without changing server files. |
| `bash setup.sh install --world my_world` | Install/start a new addon after confirmation. |
| `bash setup.sh update --world my_world` | Back up data and replace existing addon software after confirmation. |
| `bash setup.sh rollback --world my_world` | Restore the previous managed software version; retain current data/config. |
| `bash setup.sh verify --world my_world` | Check the running addon and actual game connection without an LLM request. |
| `bash setup.sh status --world my_world` | Show saved progress and service status. |
| `bash setup.sh restart --world my_world` | Restart only the addon after confirmation. |
| `bash setup.sh dialogues --world my_world` | Prepare standard dialogues using saved server paths; no translations generated. |
| `bash setup.sh adapter --world my_world` | Build the optional multiplayer translation adapter for review. |
| `bash setup.sh demo` | Run the separate demo setup/start helper. |
| `bash setup.sh advanced` | Access the older individual tools for customised workflows. |

Setup never stops, starts or replaces NWN itself. Service operations identify the
world and installation before confirmation. No system packages are installed by
the helper; a missing prerequisite is explained with a suggested correction.

Close the graphical installer with Ctrl+C in its Linux terminal. Closing setup
does not stop an installed Role Weaver service. Do not expose its temporary setup
port through a firewall or public reverse proxy; use the printed SSH tunnel.
The Server page's Browse buttons navigate the remote Ubuntu filesystem. Browser
file inputs are deliberately not used because those would select files from the
administrator's Windows computer rather than the NWN server.

## Integration and compatibility

The module is read only to report existing event assignments and resource names.
The generated folder contains one path-specific INSTALL.md, an Aurora import,
source scripts, compiled scripts when a compiler was chosen, matching NWNX header
includes, blueprints and checksums. Source-only imports must be compiled in Aurora.
A changed package, module, header or profile causes fresh preparation. Modified
output is not silently reused.

Keep existing load/chat scripts, plugin configuration and resource precedence.
Only forward approved public Talk through one chat route. HAK archives, custom
companion frameworks, store scripts and deferred chat frameworks need administrator
review; setup cannot infer their semantics. Installed file presence is checked
before deployment; loaded plugin/protocol observations come from Health & Support.
These checks do not certify arbitrary NWN/NWNX ABI compatibility.

Redis must be unauthenticated loopback on the selected port. Remote/TLS/authenticated
Redis is not currently supported. Do not weaken or redirect shared Redis services.
The installer uses systemd user services; other service managers need a manual
installation workflow. Arrange user-service persistence across logout/reboot using
your host's policy (for example administrator-configured systemd lingering).

## Optional translation

The saved translation choice adds instructions; it does not translate or index the
world. `dialogues` prepares standard DLG resources and wrappers with preserved
choices/conditions. Include effective loose overrides or extracted HAK resources
in precedence order. Custom dialogue systems are not rewritten automatically.

The multiplayer adapter currently targets Linux x86-64 NWN/NWNX **8193.37-17**.
Its build helper requires matching source/Core files, `cmake` and a C++ compiler.
The helper produces reviewable output; it does not deploy plugins or restart NWN.
After deployment enable translation on the dashboard and test in game.

## Updates, rollback and interrupted operations

Managed Python environments are versioned under the installation's `environments/`
folder. They do not depend on the package's `.venv`, so a later download can update
or roll back the service. Old environments/releases are retained for rollback.
Do not manually delete them while referenced by a current/previous service.

The update prepares dependencies before stopping the addon. It records the previous
application release and service unit in a private journal, creates a consistent
verified database recovery point, installs the new release and checks startup.
If startup fails it attempts to restore the old software service. An interrupted
operation keeps `setup-pending.json`; rerunning update/rollback recovers its recorded
service state first. If recovery fails, the journal stays for diagnosis.

Rollback applies to updates recorded by this installer, not arbitrary older manual
copies. It never restores an older player database automatically. If an older
application cannot open current data, rollback attempts to return to the current
software. Database recovery remains a separate deliberate action. Match game
scripts/plugins to the restored software during your normal maintenance process.

## Moving from the old wizard

On first configure, matching `.local/setup-addon.json` choices in the current package
are imported where possible. Existing installed ports/identity are read automatically.
You supply server/module paths once; later packages reuse the external saved profile.
If the legacy file is in another old package, run configure and enter those values.

The old `addon/setup.sh` and `addon/setup.json` remain available for advanced scripts;
they are not inputs to the new workflow. Avoid alternating between them. Legacy
installations may still reference an old package's Python environment: retain that
package until the first managed update succeeds, and retain it for rollback if the
previous service used it.

## Troubleshooting

- **FIX entries:** correct the listed path/dependency and rerun setup. Saved progress stays.
- **Compiler not selected:** choose `-` and compile the import in Aurora; dialogue preparation still needs nwnsc.
- **Dashboard port occupied:** select another for a new world. Installed worlds keep their existing port.
- **Game heartbeat missing:** finish the generated hooks, check matching Redis namespace/port and loaded plugins, then restart NWN through your usual controls.
- **Service start failed:** inspect `journalctl --user -u roleweaver-my_world.service -n 50 --no-pager`. Keep raw logs private; use Health & Support for a filtered report.
- **Need Windows dashboard access:** use the generated SSH tunnel command; never expose the administration port publicly.
