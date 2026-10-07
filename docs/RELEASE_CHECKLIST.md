# Release checklist

Release: **1.0.1**, application and Server Add-on distribution. This is a normal patch release.
Use the [review record](releases/1.0.1-review.md) for dated verification evidence.

## Package preparation completed

- [x] Separate Demo and Server Add-on archives, each with START_HERE.md.
- [x] Retain the editable three-area module, characters/lore, investigation,
  Royal Guide, merchants, patrol and both encounter examples.
- [x] Create fresh demo databases from authored content; omit player history,
  translations, credentials, private settings, native saves, logs and backups.
- [x] Include companions/templates, current bridge sources, dashboard login,
  translation adapter source, recovery and support guides.
- [x] Remove obsolete guides and update current documentation for version 1.0.
- [x] Reproducible archives, manifests, aligned versions and checksum sidecars.
- [x] Archive checks for clean seed, links, hashes, scripts and setup entry points.
- [x] NWScript compilation from extracted packages with installed dependencies.
- [x] Separate Windows Remote Installer ZIP bundles the exact verified Linux add-on.
- [x] Automated release jobs reject mismatched versions, manifests and bundled archives.

## Follow-up validation and review

These checks remain open; publishing version 1.0 does not mark them passed.

- [ ] Fresh Ubuntu installation following only the included instructions.
- [ ] Upgrade/rollback rehearsal on a copy of an existing installation.
- [ ] Final player walkthrough: guide, investigation, merchants, both encounters,
  familiar chat/items/visits, translation and restart continuity.
- [ ] Independent existing-server integration on a modified staging world.
- [ ] Inherited creature/module asset provenance review in THIRD_PARTY_NOTICES.md.
- [ ] Previously deferred real crash/recovery, extended runs and multiplayer scenarios.
- [ ] Further developer readability/documentation and supported-environment review.
- [ ] Resolve significant reports from external server owners.

## Publication procedure

Commit the reviewed source, tag it `v1.0.1`, and build both packages from that
exact source. Upload archives and checksums to a normal GitHub release, make it
latest, and verify the public downloads. Do not mark it as a prerelease.
Forum and Vault announcements are separate actions controlled by the owner.

A clean distribution does not reset the installed test world's databases or
restart its game server. Installation instructions explain how to activate updates.
