# Make the demo your own

All authoring inputs are editable files. The generated instance is separate from them.

| File or folder | What you edit |
| --- | --- |
| `demo/world/YourWorld.mod` | Source world in the NWN toolset |
| `demo/content.json` | NPC IDs, profiles, positions, public lore and shop permissions |
| `demo/PLAYTEST.md` | Gameplay scenarios |
| `demo/LLM_COMPARISON.md` | LLM test protocol and expected behavior |
| `demo/results-template.csv` | Result-sheet columns |
| `.demo/rw_demo/` | Generated local runtime/data; never distribute this directory |

## Edit or replace the world

Stop the demo with Ctrl+C. Back up the source module, then edit it in the toolset. Keep the filename
or replace its contents with your own clean module. Keep its original load/chat handlers: the builder
wraps them. Modules already containing Role Weaver's reserved scripts need manual integration.
Use `--module /path/to/CleanWorld.mod` during a new setup to choose a different source path.

If the starting area or creature blueprint changes, update `area_tag` / `blueprint` in content.json.
`area_tag` is the area's **tag**, not necessarily its resource filename. Set x/y positions to walkable
locations. Every listed NPC uses the chosen blueprint; customize race/class/appearance in the dashboard
or extend the authored spawn script later. Lore text alone does not change the map.

Recompile your saved source into the existing instance:

```bash
python demo/demo.py check-content
python demo/demo.py rebuild
```

Rebuild preserves data, provider settings and passwords. It backs up previous active module/override
files under `.demo/rw_demo/previous-builds/`. Restart to load the new world. Replacing an area's tag may
invalidate saved placements/destinations: check those in the dashboard before resuming AI.

## Edit NPCs and lore

Stable NPC IDs connect a creature to its profile and memories. Keep the same ID when editing a character;
use a new ID for a genuinely different character. JSON must use normal double quotes and no comments.

For an existing stopped instance, deliberately import your edited templates:

```bash
python demo/demo.py apply-content
```

This backs up the database, updates listed profiles and public lore documents, enables auto mode and
replaces the listed NPCs' action permissions with the demo defaults (greet plus shop if selected).
It preserves conversations, memories and unlisted profiles/documents. Removed entries are **not**
deleted automatically: remove them in the dashboard when desired. Dashboard edits are not written back
to content.json. Back up before importing if you wish to retain those edits.

Changing names, positions or the NPC list also requires `rebuild` so native creatures match the templates.
Applying content while the launcher is running is refused. Do not run the same instance separately as
a system service; the demo lock only coordinates this launcher.

## Fresh test instances

Use a new instance name and unused ports for clean memory and inventory:

```bash
python demo/demo.py setup --instance comparison_a --game-port 5126 --web-port 8746 --native /your/dependencies --compiler /your/nwnsc --guardrails
python demo/demo.py start --instance comparison_a
```

Each has a separate Redis prefix, database, userdata and credentials. Do not reuse ports with a running
world. Changing models in one existing instance retains memories, which can bias comparisons.

## Build a distributable archive

From the repository root:

```bash
python tools/package_demo.py
```

The archive and checksum appear in `dist/`. Rebuild after modifying the source world, content or guides.
The packager excludes `.demo`, local configuration, keys, databases, compiler links and native runtime.
An archive manifest records the SHA-256 of every packaged input. Check module/custom-asset redistribution
permissions before publicly distributing your revised world.
