# Guided Linux setup

Run **`bash setup.sh`** from the extracted package. The same launcher is included
in the separate demo and existing-server distributions. Run it as the Ubuntu
account that owns the installation, not with sudo.

The wizard asks for paths, validates world IDs/ports, and offers defaults. Paths
can contain spaces and may begin with `~`. API keys are entered later in the
dashboard, never into the wizard. Choose **0** or press Ctrl+C to leave.

| Menu choice | What it does |
| --- | --- |
| 1. Prepare an existing server | Saves six non-secret settings and creates an Aurora import with matching NWNX headers. Prints the next guide to read. |
| 2. Prepare/start demo | Checks separate dependency folders, creates local links, builds a demo copy and optionally starts it. Reusing an instance starts its saved world. Available only in the demo/source package. |
| 3. Check addon prerequisites | Uses saved settings to check Linux, systemd and the local Redis connection. |
| 4. Install/start addon | Uses the existing installer; preserves installed configuration/data, creates a recovery point before upgrading, and refuses an active service. |
| 5. Restart addon | Restarts only the selected Role Weaver service. Does not restart NWN. |
| 6. Service status | Shows systemd status for the saved world. |
| 7. Prepare dialogues | Reads an existing module and optional effective loose resource folders, compiles wrappers, and creates a new review bundle. No LLM or cache calls. |
| 8. Build translation adapter | Builds a production plugin against administrator-selected matching NWNX sources/Core. Generates path-specific installation instructions. |

## Dependencies and environment

The helper can create `.venv` and install the project's Guardrails requirements
after asking. On Ubuntu install `python3-venv` first. Redis must be installed and
running locally; existing authenticated/external Redis arrangements may need a
separate private instance. See [transport compatibility](../addon/COMPATIBILITY.md).
The helper does not alter Redis or system packages.

NWN and matching NWNX binaries/headers must already be installed. Use
[new server setup](../addon/NEW_SERVER.md). The Demo download also includes a
dedicated `demo/DEPENDENCIES.md` guide.
The demo links your actual folders into `.local/native/INSTANCE/`; existing links
are accepted only when they already point at the selected directories. No runtime
files are moved. Keep the selected dependencies at those paths.

## Existing-server settings and upgrades

Wizard choices are saved in `.local/setup-addon.json`, with the previous copy in
`.local/setup-addon.previous.json`. They are excluded from release packages and Git.
The advanced `addon/setup.sh` interface still defaults to `addon/setup.json`.
To use the wizard file from the advanced interface, pass it explicitly:

```bash
bash addon/setup.sh check --config .local/setup-addon.json
```

When a selected world already has an installation, the wizard reads its existing
namespace/ports and refuses different ones. The installer retains its complete
configuration and credentials. An upgrade is not a way to rename an existing world.

For upgrades, keep the old package available, extract the new one, copy
`.local/setup-addon.json` into the new package's `.local/` folder, prepare its Python
environment, and check prerequisites. Stop the intended addon service during your
maintenance window, then choose **4**. It creates a verified database snapshot.
Use [operations](../addon/OPERATIONS.md) for service and rollback details. Bridge
or plugin changes still require a separate game-server maintenance restart.

## Translation integration

Use **1** to prepare the updated bridge before **7**. The dialogue helper asks for
the real module path, generated bridge source folder, runtime, headers and compiler.
Start with one standard dialogue resource if desired. Add effective loose override
or extracted HAK folders in precedence order. Archives and custom conversation
systems are not discovered automatically. Review the token range for conflicts.

The per-viewer adapter currently targets **Linux x86-64 NWN/NWNX 8193.37-17** only.
Option **8** asks the administrator to confirm that exact version and checks the
selected source/Core files. It cannot prove ABI compatibility. It needs `cmake`
and a C++ toolchain (`sudo apt install build-essential cmake` on Ubuntu).
It explicitly disables native test entry points in the generated production build.

Neither option installs into a running server. Each outputs an **INSTALL.md** with
the next steps. Keep the module's original conditions, actions, quests and event
handlers. After installing and restarting NWN, use **Translations** and **Health &
Support** to check the worker, queue and actual bridge/plugin observations.

Existing manually prepared demo instances are not rebuilt automatically. Use their
documented rebuild procedure during maintenance when game scripts change.
