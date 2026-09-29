# Alpha 0.3.0 — translation, recovery and easier setup

Prepared distribution: **Alpha 0.3.0**. Application runtime: **0.28.0**.
Proposed prerelease tag: `v0.3.0-alpha.1`. Packaging does not publish a release.

## Choose a download

- **RoleWeaver-Demo-Alpha-0.3.0.tar.gz**: a separate, editable Kingdom of Role Weaver demo, investigation, NPC profiles/lore and optional playtests.
- **RoleWeaver-Server-Addon-Alpha-0.3.0.tar.gz**: the service and integration tools for an existing NWN:EE/NWNX server. Your module stays in its own location. The supplied example world is optional.

Extract on Linux, read **START_HERE.md**, then run **`bash setup.sh`**.
Ubuntu 24.04 / Python 3.12 is the tested environment. NWN server files, matching
NWNX plugins/headers, Redis and `nwnsc` remain separate prerequisites. The guides
cover new installations and existing dependency folders. Players use NWN:EE on
their usual computer; the addon dashboard is for server owners and DMs.

## Changes since Alpha 0.2.0

- **On-demand world translation.** Players select a language and enable/disable it with `/rw language` in Talk. Supported examination text, public NPC/player biographies, object labels and prepared standard NPC dialogues use a shared translation cache. Changed source text requires a new translation. Player names, chat, tells and logs are excluded.
- **Private translations.** Examination uses a private reading window with original/translated text switching. The optional native adapter sends standard dialogue in each viewer's language; public spoken chat retains the server language. Different-language players have been tested together.
- **Translation diagnostics.** See worker and queue status, rate-limit waits, cache counts, recent errors, request usage and content-free diagnostic downloads in Translations. Preparation makes no LLM calls; only requested text is translated.
- **Database recovery.** Verified, rotating snapshots cover world data, the translation database, usage and player identity salt. The dashboard offers integrity checks and restore previews; an independent recovery page remains available when normal database startup fails.
- **Health & Support.** Connection, worker, observed bridge/plugin, database, backup and recent provider status in one panel, with filtered support reports and bounded rotating error logs.
- **Guided setup.** One launcher asks for dependency paths and world settings, prepares Aurora imports, checks prerequisites and manages the addon service. Optional steps prepare existing dialogues and build the translation adapter.
- **Demo bridge correction.** Rebuilds now use the package's current bridge scripts instead of older scripts embedded in the editable module, while preserving authored area layout and story hooks.

Existing AI NPC, merchant, inventory, live encounter and persistent AI DM features
remain available. This release retains the current small demo; the larger demo,
code readability work and expanded developer documentation are planned before 1.0.

## Updating an existing installation

1. Keep the old package. Back up addon data and your game's module, scripts, HAKs,
   character/campaign data and launcher separately. Database snapshots do not
   contain NWN game files or credentials.
2. Extract the new package into a new folder. Copy your non-secret wizard settings
   (`.local/setup-addon.json`) or manual settings (`addon/setup.json`) into the
   same relative location. Keep the existing world ID, Redis prefix and ports.
3. Follow **START_HERE.md** and **addon/OPERATIONS.md**. Stop only the selected
   addon service before upgrading. The installer preserves its installed config,
   credentials and data, and makes a verified recovery snapshot first. Retain the
   old Python environment until the upgrade succeeds.
4. Prepare and review a fresh bridge import. Preserve your world's event handlers.
   Schedule a game restart to activate the updated scripts; updating Python alone
   is insufficient. Do not replace an established world with the example module.
5. Translation is off by default. Configure the provider and enable it in the
   dashboard. Standard dialogues require offline preparation. For independent
   multiplayer dialogue translation, build/install the optional adapter and
   recompile prepared wrappers against this bridge, then restart NWN.

For the demo, a fresh instance in the newly extracted package gives an isolated
test world. Keep an existing `.demo/` folder with its old package until you have
backed it up. Reusing an existing instance does not rebuild game scripts
automatically; follow the demo's customization/rebuild instructions deliberately.

## Compatibility and limitations

- Linux alpha; no native Windows server package. The optional **NWNX_RWTranslation**
  adapter targets **Linux x86-64 NWN/NWNX 8193.37-17** and requires matching sources
  and Core. Its source is included; no compiled native plugin is bundled. Without
  it, standard dialogue falls back to original text when another player is in the
  area. A successful C++ build alone does not establish ABI compatibility.
- First requests may show original text. Reopen after translation finishes.
  Preparation preserves standard dialogue choices, scripts and conditions; custom
  conversation systems, journals, quest text, boards and menus need separate
  integration. HAK resources are not automatically extracted or catalogued.
- Backups cannot protect against loss of the disk containing them. Download a copy
  elsewhere. Restore replaces saved addon state and requires NWN to be stopped;
  it is not an atomic rollback of the entire game world.
- Provider quality, latency, quotas and pricing vary. Guardrails are not guarantees.
  Translation rate limits count jobs, not every fallback HTTP request or currency
  spent. Costs are estimates based on configured rates and reported usage.
- Keep the dashboard and Redis private; use an SSH tunnel. No public-dashboard
  authentication or internet-facing deployment is promised by this package.

## Validation and reporting

Focused application/package checks, bridge compilation and prior in-game testing
support this alpha. Two players using German and Spanish tested per-viewer
dialogue successfully. New-package clean-install/upgrade rehearsals, deliberate
interruption/recovery exercises, further multiplayer scenarios and extended runs
are **deferred at the project owner's request**, not claimed as passed.

The release review also retains an open provenance review for the inherited
creature blueprint and supplied module's third-party content; see
**THIRD_PARTY_NOTICES.md**. Packaging is not a declaration of asset clearance.

Try the optional demo playtests and LLM/Guardrails comparisons. For reports,
include the package/runtime versions, NWN/NWNX build, model, settings and steps.
Health & Support can download a filtered support ZIP; Translations can download
content-free diagnostics. Review attachments before sharing. Do not send keys,
database backups, raw logs or private player conversations.

Source and issues: https://github.com/RoleWeaverInfo/roleweaver-server
