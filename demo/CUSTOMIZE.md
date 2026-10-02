# Make the demo your own

All authoring inputs are editable files. The generated instance is separate from them.

The development world includes a forest path and cave connected to the throne
room. See [Encounter areas](ENCOUNTER_AREAS.md) for door locations, staging points
and editing instructions.

| File or folder | What you edit |
| --- | --- |
| `demo/world/YourWorld_Fixed.mod` | Source world in the NWN toolset |
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
.venv/bin/python demo/demo.py check-content
.venv/bin/python demo/demo.py rebuild
```

Rebuild preserves data, provider settings and passwords. It backs up previous active module/override
files under `.demo/rw_demo/previous-builds/`. Restart to load the new world. Replacing an area's tag may
invalidate saved placements/destinations: check those in the dashboard before resuming AI.

## Custom HAKs and TLKs

Stop the demo before adding content. Put required HAK files under
`.demo/rw_demo/userdata/hak/` and TLKs under `.demo/rw_demo/userdata/tlk/`, creating
those folders if necessary. Set the module's HAK/TLK requirements in Aurora and
provide matching client files to players. Rebuild the edited module before restarting.
These are your local additions and are not collected by the release packager.
Check redistribution permissions before including custom content in a public demo.

## Edit NPCs and lore

Stable NPC IDs connect a creature to its profile and memories. Keep the same ID when editing a character;
use a new ID for a genuinely different character. JSON must use normal double quotes and no comments.

For an existing stopped instance, deliberately import your edited templates:

```bash
.venv/bin/python demo/demo.py apply-content
```

This backs up the database, updates listed profiles and public lore documents, enables auto mode and
replaces the listed NPCs' action permissions with their supplied demo settings.
It preserves conversations, memories and unlisted profiles/documents. Removed entries are **not**
deleted automatically: remove them in the dashboard when desired. Dashboard edits are not written back
to content.json. Back up before importing if you wish to retain those edits.

Changing names, positions or the NPC list also requires `rebuild` so native creatures match the templates.
Applying content while the launcher is running is refused. Do not run the same instance separately as
a system service; the demo lock only coordinates this launcher.

## Clean an existing demonstration

New demo installations contain only the supplied cast and the two forest/cave
encounters. They do not import development logs, conversations, keys or databases.
The King remains part of the cast because the investigation summons him; the Royal
Guide is a normal module NPC used to demonstrate translated dialogue.

To tidy your own **demo** after testing, stop the game and add-on first. From the
extracted demo folder, preview the cleanup:

```bash
.venv/bin/python demo/cleanup.py --data-dir .demo/rw_demo/data --world-id rw_demo
```

Review the NPC IDs it will remove, then repeat with `--apply` to make the changes.
Use your instance name in both places if you chose a different one. This tool is
for disposable demos, not an existing persistent world: it removes profiles and
lore absent from `demo/content.json`, past live scenes, unused destinations and
old encounter definitions. It rearms the two supplied encounters from their first
stage, clears usage and safeguard activity, and archives support logs.

It makes a private `before-demo-cleanup-*` backup beside the data folder. Kept NPCs
retain their conversation memory; earlier conversations are hidden from the
dashboard activity view. Translations, player language preferences, provider keys,
price settings and saved placements are preserved. Cleanup does not revive dead
creatures or move them. Start the demo again when finished.

Do not include the private recovery folder or `.demo` in a release. The package
builder uses authored source files only.

## Fresh test instances

Use a new instance name and unused ports for clean memory and inventory:

```bash
.venv/bin/python demo/demo.py setup --instance comparison_a --game-port 5126 --web-port 8746 --native /your/dependencies --compiler /your/nwnsc --guardrails
.venv/bin/python demo/demo.py start --instance comparison_a
```

Each has a separate Redis prefix, database, userdata and credentials. Do not reuse ports with a running
world. Changing models in one existing instance retains memories, which can bias comparisons.

## Build a distributable archive

From the repository root:

```bash
.venv/bin/python tools/package_demo.py
```

The archive and checksum appear in `dist/`. Rebuild after modifying the source world, content or guides.
The packager excludes `.demo`, local configuration, keys, databases, compiler links and native runtime.
An archive manifest records the SHA-256 of every packaged input. Check module/custom-asset redistribution
permissions before publicly distributing your revised world.

## Investigation module

The supplied world already includes Role Weaver and investigation hooks. Keep `scenario: "investigation"` in `demo/content.json`; setup recompiles those scripts for the demo namespace while retaining your area edits. The four placed witnesses have `spawn: false`; the King is summoned by the story. The innkeeper, merchant and four encounter actors use additional demo spawn entries. An NPC's optional `area_tag` selects its area; omitting it uses the top-level area. After moving landmarks in Aurora, update `controlled_actions.destinations` and the affected NPC coordinates in `demo/content.json`, then stop, rebuild and apply-content. Back up `.demo/rw_demo` before applying content because it replaces supplied authoring profiles and lore, while retaining memories.

The optional `encounters` list defines the forest robbery and cave hostage scenes
described in [ENCOUNTER_AREAS.md](ENCOUNTER_AREAS.md). Setup arms enabled scenes in
a fresh database. Reimporting content updates their templates but preserves existing
run snapshots and progress. To use a changed template for an existing run, cancel
and arm it again through Persistent Encounters. Each actor's `combatant` flag
controls whether the encounter may order that actor to attack the player; keep it
`false` for the hostage. This requires bridge encounter protocol 7 or newer.

## Saved dashboard setup

The supplied content.json includes the saved NPC profiles, lore/access settings, approved destinations, innkeeper/merchant spawn positions and facing, conversation/hearing controls, safeguard settings and merchant haggle rules maintained with this release. Setup applies these to a fresh instance. apply-content imports these authoring settings into an existing stopped demo after backing up its database; it preserves player memories. Provider credentials and player histories are not included. The optional example-world content in the add-on archive is the same authored content.
