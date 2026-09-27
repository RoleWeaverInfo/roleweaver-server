# Alpha 0.2.0 — AI DM encounters and expanded NPC behaviour

Distribution tag: `v0.2.0-alpha.1`. Application runtime: `0.27.0`.

## Two downloads

- **Demo**: editable Kingdom of Role Weaver investigation world, launcher, playtests and example encounters.
- **Server Add-on**: companion, integration scripts and instructions for an existing NWN:EE/NWNX world. The supplied example module is optional; your own module stays in its existing location.

Both are Linux alpha packages. Ubuntu 24.04 is the tested environment. NWN, NWNX, Redis and the script compiler are supplied separately; follow the package's START_HERE.md. Players can connect using their normal Windows NWN client.

## Changes since Alpha 0.1.0

- Separate live and persistent encounter workspaces, AI-assisted proposals, scene direction, stages and outcomes.
- Persistent AI DM monitoring and approved restart recovery without an online DM; live placement, triggers, preview and cleanup.
- Native social checks for persuasion, intimidation and bluff; bounded warnings, combat, retreat and encounter reset.
- NPC perception, movement toward visible objects and characters, patrol/check-ins and optional village-life activity.
- Inventory inspection, container interactions, fetch/deliver, exchanges, equipment and permitted item use.
- Explicit player gold payment through the existing exchange window, with confirmed receipts; optional NPC-to-NPC combat permissions.
- Robbery and troll-hostage example profiles, proposal text and playtest guidance. Examples are opt-in and do not spawn or arm themselves.

## Updating

Back up the companion data, module and scripts first. Existing-server owners should use START_ADDON.md and prepare a fresh bridge bundle with the new source. Review and apply the integration hooks, compile the scripts, and restart the companion and NWN to load the update. Updating only Python leaves the new controls unavailable. Preserve your world ID, Redis prefix, configuration, provider credentials and data directory. Do not overwrite an existing world with the sample module.

New payment and NPC-combat permissions default to off. Configure them explicitly. Existing paused encounters are not silently armed. Persistent actor placement and encounter automation are separate settings.

## Testing and limitations

The Python suite and dashboard JavaScript checks cover policies, parsing, receipts, encounter recovery and package boundaries. Native tests were run against the Ubuntu test server for bridge compilation and payment/permission handling. New example profiles require in-game balancing and playtesting; troll appearance is not a complete stock troll stat block or a regeneration implementation. No party-level balancing is promised.

LLM behaviour varies by model. Guardrails and natural-language scene boundaries are not guarantees; scripts enforce supported permissions and transactions. Combat remains controlled by NWN and world scripts. Payment exports the character after confirmation, but does not provide an atomic crash-proof transaction across all game and companion saves. Hosted public service, automatic rewards and a general quest scripting engine are not included.

Try the demo's PLAYTEST.md and LLM_COMPARISON.md, then the example encounter checklists. Include package/runtime version, NWN/NWNX versions, model, relevant settings and reproduction steps in reports; remove credentials and private player information.
