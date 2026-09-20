# Alpha release checklist

Alpha validation record. Unchecked items remain limitations of this prerelease.

- [x] Separate source repository with existing MIT license preserved.
- [x] Domain-oriented service modules and consistently formatted Python source.
- [x] Developer setup, architecture, bridge and contribution documentation.
- [x] Automated regression workflow without real API keys or game data.
- [ ] Review demo module and every bundled asset's redistribution rights.
- [x] Package the supplied editable world with example NPCs, lore, merchant and approved greeting/shop actions.
- [x] Demo setup with explicit dependency paths, validation and foreground start/stop instructions.
- [x] Guided existing-server integration, editable setup files and generated Aurora import resources.
- [ ] Redacted rotating error logs and diagnostic-report export.
- [ ] Clean Ubuntu installation test using only published instructions/artifacts.
- [ ] Test upgrade and rollback on a copy of an existing world.
- [ ] Publish versioned prerelease archives, checksums, known limitations and support instructions.

The investigation was deployed and playtested on the project Ubuntu VM. Generated add-on scripts compiled with that installation's matching NWNX headers. Clean-machine installation and manual Aurora import of the new ERF still need testing. Source CI does not validate native runtime compatibility.
