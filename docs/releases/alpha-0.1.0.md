# Demo Alpha 0.1.0

The editable Kingdom of Role Weaver investigation includes YourWorld_Fixed.mod, six starting NPCs, a summoned King, individual backgrounds, public/restricted lore, a merchant, approved destinations and the latest saved dashboard authoring setup.

## Download and run

Download **RoleWeaver-Demo-Alpha-0.1.0.tar.gz** and its **.sha256** file from the [GitHub prerelease](https://github.com/RoleWeaverInfo/roleweaver-server/releases/tag/v0.1.0-alpha.1). Verify with `sha256sum -c RoleWeaver-Demo-Alpha-0.1.0.tar.gz.sha256`, extract the archive and open START_HERE.md.

NWN/NWNX and compiler binaries are external prerequisites. The demo defaults to game UDP 5125 and loopback dashboard TCP 8745. API keys and player databases are not bundled.

## Help test

Talk to Captain Beran and examine the noticeboard. Collect witness accounts, request an audience and present your conclusion to the King. Try shopping, haggling, directions and memory after reconnecting. The investigation resets each login; personal conversation memories remain.

Compare models for natural dialogue, distinct personalities, consistent lore, memory and response time. Test guardrail bypasses and false positives using synthetic data. See the [model comparison guide](../../demo/LLM_COMPARISON.md) and [playtest checklist](../../demo/PLAYTEST.md).

Report the exact provider/model, guardrail settings, test message, response and reproduction steps in [Issues](https://github.com/RoleWeaverInfo/roleweaver-server/issues). Remove API keys and private player information.

## Validation and limitations

- Application regressions, formatting and browser draft-recovery checks are run before release. CI checks Linux with and without optional Guardrails dependencies.
- The edited world compiled and ran on the project Ubuntu VM. All 11 generated add-on entry scripts compiled with the collected NWNX headers.
- Clean-machine setup, manual Aurora import of the new ERF, and heavily customized persistent worlds need wider testing.
- Model behavior, latency, availability and costs vary. Guardrails cannot guarantee every unwanted response will be caught. Cost estimates depend on configured pricing.
- The demo uses a foreground launcher, not a production hosting service. Keep the dashboard and Redis private; back up before testing upgrades or restores.
- The source also includes the separate server-owner installer and documentation. YourWorld_Fixed already has story hooks; do not replace them with the generic add-on templates.
- Existing third-party/asset notices remain applicable. Alpha 0.1.0 is the package version; the internal runtime remains 0.26.7.
