# Alpha release checklist

Alpha 0.3.0 review record. Unchecked items remain limitations of this prerelease.

- [x] Separate source repository with existing MIT license preserved.
- [x] Domain-oriented service modules and consistently formatted Python source.
- [x] Developer setup, architecture, bridge and contribution documentation.
- [x] Automated regression workflow without real API keys or game data.
- [ ] Review demo module and every bundled asset's redistribution rights.
- [x] Package the supplied editable world with example NPCs, lore, merchant and approved greeting/shop actions.
- [x] Demo setup with explicit dependency paths, validation and foreground start/stop instructions.
- [x] Guided existing-server integration, editable setup files and generated Aurora import resources.
- [x] Allowlisted rotating error logs and diagnostic-report export (see [Health & Support](HEALTH_AND_SUPPORT.md)).
- [x] Translation diagnostics, on-demand caching and guided dependency paths.
- [x] Demo rebuild uses current bridge sources, preserving authored world layout.
- [x] Separate Alpha 0.3.0 archives, checksums, release notes and package version metadata prepared.
- [ ] Clean Ubuntu installation test using only published instructions/artifacts.
- [ ] Test upgrade and rollback on a copy of an existing world.
- [ ] Publish versioned prerelease archives, checksums, known limitations and support instructions.

The investigation was deployed and playtested on the project Ubuntu VM. Generated add-on scripts compiled with that installation's matching NWNX headers. Clean-machine installation and manual Aurora import of the new ERF still need testing. Source CI does not validate native runtime compatibility.

Interruption/recovery exercises, additional multiplayer scenarios, extended runs
and clean-install/upgrade rehearsals are deferred at the project owner's request.
Focused release checks do not stand in for those exercises. See
[Alpha 0.3.0 notes](releases/alpha-0.3.0.md) and the
[release review record](releases/alpha-0.3.0-review.md).
