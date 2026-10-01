# Developer setup

## 1. Choose the scope

The dashboard and regression tests can run without NWN. Native gameplay requires Linux, NWN:EE
server files, NWNX:EE and Redis. Ubuntu 24.04 / Python 3.12 is the current tested baseline; Docker
is not required. Windows can run core Python tests, but native game integration is tested on Linux.

## 2. Create an isolated Python environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests
```

On Windows activate with `.venv\Scripts\Activate.ps1`. The core application uses Python's standard
library. Developer tools and optional Guardrails have separate requirement files.

For the full validation suite:

```bash
python -m pip install -r requirements-guardrails.txt
python -m unittest discover -s tests
```

Without those packages, optional Guardrails tests are skipped; inspect the test summary.
`test_*.py` tests use temporary storage and mocks. `live_*.py` scripts are separate native integration
harnesses: read their arguments and prerequisites before running them.

## 3. Start an offline dashboard

```bash
mkdir -p .local
cp config.example.json .local/config.json
python -m roleweaver.web --config .local/config.json
```

Open http://127.0.0.1:8743. Data is stored next to the configuration in `.local/data/`.
The bridge will show disconnected without Redis and an integrated game world. This does not mean
that the dashboard failed. Stop with Ctrl+C. No credentials are required for offline mode.

For a local Redis process on Ubuntu, install/start your Redis package and keep it bound to loopback.
Use a unique `world_id` and `redis_prefix` per world; never point development at a live world's queue.
Configure online providers in the dashboard. Do not add keys to the example config or source tree.

## 4. Native game development

The repository does not include the NWN runtime, NWNX shared libraries, compiler, or YourWorld.mod.
Obtain a compatible NWN:EE dedicated server and matching NWNX:EE plugins/headers independently.
The current build helper expects an executable `tools/nwnsc` and a native runtime directory.
Run `python tools/build_addon.py --help` for its arguments and read [integration](INTEGRATION.md).
The helper builds a review bundle, not an automatic production deployment.

Before installing any compiled scripts, back up your module, override scripts, configuration and
campaign databases. Preserve your world's load/chat handlers. Use a separate NWN port and Redis
prefix for the test world. Do not copy compiled scripts into a running production module.

## 5. Format and validate

```bash
python -m black roleweaver tools tests
python -m black --check roleweaver tools tests
python -m unittest discover -s tests
```

CI runs the core and optional-Guardrails configurations on Ubuntu/Python 3.12. Native playtests are
manual and are not implied by a green CI run. See [testing](TESTING.md).

## Encounter preview

See [DM encounters](ENCOUNTERS.md) for the editor, information boundaries, combat
controls, code map and playtest checklist.

See [Live Encounters](LIVE_ENCOUNTERS.md) for temporary placement, frozen previews,
ownership-scoped cleanup, recovery behavior and the separate API.

[NPC perception](PERCEPTION.md) documents the bounded game scan, shared prompt/inspector
snapshot, player anonymity and freshness checks.

See [Nearby behaviour and permissions](NEARBY_BEHAVIOUR.md) for dynamic movement, doors, seating, and NPC visits.

## Inventory tasks

See [Inventory, exchange and assistance](INVENTORY_TASKS.md) for the game-owned
transfer boundary, permissions and native regression fixture. Python choices
live in `roleweaver/inventory.py`; native checks are in `bridge/rw_inventory.nss`
and the per-window NUI confirmation handler is `bridge/rw_trade_evt.nss`.

### Creature creation and restore positions

`RWCreateCreature` reads `rw_base.utc` with `TemplateToJson`, then creates only
one final creature. Do not recreate the former temporary seed at the destination:
`DestroyObject` is deferred, so the seed still occupies the spawn point and the
engine collision adjustment is saved as a new persistent position on each restart.
Runtime-only GFF fields such as `BaseAttackBonus` and `xStartingPackage` need
explicit types because they may be absent from the blueprint.

`tests/placement_native.nss` runs five create/save/destroy/recreate cycles in a
disposable copy of the throne-room module, reporting step and accumulated drift.
Compile it as `invtest` and use an isolated module-load hook/userdata/port as for
the inventory fixture. Never run regression fixtures in the live world. Genuine
obstacles can still cause normal engine relocation; do not force actors through
walls or overwrite deliberate DM movement to compensate for old drift.


Village Life scheduling lives in `roleweaver/village.py`; game-side boundaries and
movement use `bridge/rw_actions.nss`. See [Village Life](VILLAGE_LIFE.md) for setup.
`tests/test_village.py` checks interruption priorities and restart behaviour.
`tests/village_native.nss` is a disposable-world movement fixture, never a live
module hook. Capture starting locations before DelayCommand, not inside its
deferred arguments.

### Autonomous scene director

`roleweaver/director.py` owns the reusable bounded response schema and reasoning
prompt. It has no access to placement, persistence, Redis or game commands.
`roleweaver/live_director.py` adapts live scene state, recent scoped dialogue and
confirmed native observations into that prompt, schedules bounded background reviews,
and applies only actor goals or checked resolution. `dm_assistant.request` supplies
provider transport; usage is recorded as `live_director`.

`bridge/rw_encounter.nss` supplies protocol 4 presence observations, escalation hold
and the owner/token/epoch checked end command. Native scripts never accept an LLM
chosen target or script name. `tests/test_director.py` covers stale reviews, scoped
transcripts, pause behavior, error backoff, output validation and confirmation.
`tests/conversation_combat_native.nss` must run only in a disposable test module.

### Optional social resolver

See [Social checks](SOCIAL_CHECKS.md) for the classifier, NWN adapter and native
protocol 5 boundary. It resolves Intimidate, Persuade and Bluff before dialogue;
combat remains separate. The game reads effective skills and rolls dice, while
the model can only identify intent. The persisted attempt ledger and native cache
prevent retries from generating extra rolls.

### Player companions

See [Familiar prototype](COMPANIONS.md) for the opt-in chat workflow, owner-bound
protocol, stock associate adapter and PW extension points. This layer has no
world-NPC placement or respawn behavior. `rw_address.nss` shares conservative
name-address parsing between familiar and world-NPC chat. `rw_talk_inc.nss`
owns the small focus-cancellation seam so click-to-talk can cancel a pending
familiar turn immediately. `RWCPObserve` samples the same read-only visibility
checks as world NPCs; `roleweaver.perception.snapshot` removes private transport
metadata and rejects stale observations before they enter provider context.

Familiar cargo is a native, owner-carried satchel rather than a second serialized
inventory. `rw_cp_pack` handles bag ownership and native transfer rules;
`rw_cp_items` offers bounded errands and validates movement; `rw_cp_ui` handles
owner confirmation and recipient consent. `companion_inventory.py` projects only
eligible item labels and offered action IDs into model context. Inventory
snapshots are not persisted in the Role Weaver database. Native character saves
and PW world persistence remain responsible for the actual items; database
backups alone cannot restore these possessions. See the companion guide for
configuration, lifecycle limits and isolated native test fixtures.
