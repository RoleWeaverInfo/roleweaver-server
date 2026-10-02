# After version 1.0

## Release maintenance

Version 1.0 provides two downloads: the editable demonstration and the service
for existing NWN/NWNX servers. Both include source, documentation and checksums.
New demos start with authored content and empty player/translation databases.

Prioritize installation reliability, compatibility with modified worlds, recovery,
bounded LLM usage and clear troubleshooting. Use server-owner feedback and the
[release checklist](RELEASE_CHECKLIST.md) to guide maintenance releases.
Deferred clean-machine, extended multiplayer and real interruption/recovery
checks remain open until performed; a version number does not mark them passed.

## Developer preparation

Keep tagged source available to contributors. Refactor larger Python, browser and
NWScript components incrementally, document interfaces and add extension examples.
A dedicated developer bundle should offer more than the source checkout.

## Further development

Expand the demo after its current examples are reliable. Keep live and persistent
encounters distinct. Additional companion frameworks and translation of custom
journals, quests, boards and menus remain separate integrations because worlds
implement these differently.
