# Alpha release checklist

This is a release plan, not a claim that the demo/installer is ready.

- [x] Separate source repository with existing MIT license preserved.
- [x] Domain-oriented service modules and consistently formatted Python source.
- [x] Developer setup, architecture, bridge and contribution documentation.
- [x] Automated regression workflow without real API keys or game data.
- [ ] Review demo module and every bundled asset's redistribution rights.
- [x] Package the supplied editable world with example NPCs, lore, merchant and approved greeting/shop actions.
- [x] Demo setup with explicit dependency paths, validation and foreground start/stop instructions.
- [ ] Guided existing-server integration preserving original event handlers.
- [ ] Redacted rotating error logs and diagnostic-report export.
- [ ] Clean Ubuntu installation test using only published instructions/artifacts.
- [ ] Test upgrade and rollback on a copy of an existing world.
- [ ] Publish versioned prerelease archives, checksums, known limitations and support instructions.

The currently running test installation remains separate from this refactor until it has been
explicitly installed and playtested. Source CI does not validate native runtime compatibility.
