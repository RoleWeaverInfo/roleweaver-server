# Alpha 0.3.0 and path toward 1.0

The current development work keeps existing translation surfaces. Custom journals,
quest descriptions, message boards and custom menus will be considered separately;
worlds implement these through different systems.

## Next alpha preparation

- Database recovery and health/support reporting are implemented.
- Owner-facing translation diagnostics and a guided installation entry point are implemented.
- Include both demo and existing-server packages, matching bridge resources,
  optional native adapter source, setup instructions and known limitations.
- Review package contents, version labels, documentation and release notes before
  building/publishing a new tagged alpha. Do not overwrite Alpha 0.2.0 labels with
  unreleased feature claims.
- Record validation honestly. Interruption/recovery exercises, additional
  multiplayer scenarios, extended-running tests and fresh-install/upgrade
  rehearsals are **deferred at the project owner's request**, not marked passed.
  Focused code/package checks can still cover the changes being prepared.

## Expanded demo before 1.0

After this alpha is packaged, develop a more elaborate editable demo that shows
NPC behavior, AI DM live and persistent encounters, translation and recovery in
clear scenarios. Keep the current small investigation as the Alpha 0.3.0 baseline.
Plan the new locations, characters and scenarios with the project owner before
changing the world.

## Developer readability and packaging before 1.0

After this alpha scope is settled, review the code by domain, extract large mixed
responsibilities, document interfaces and invariants, improve names/comments, and
provide a developer package with reproducible setup and extension examples. Keep
changes incremental so behavior remains reviewable. Preserve the separate live
and persistent encounter modes and the engine-independent AI/rules boundaries.

## Toward 1.0

Use alpha feedback to prioritize correctness, installation compatibility and
maintainability. Revisit the deferred validation before claiming production
readiness. A 1.0 release should have a defined supported environment, migration
and recovery procedures, clear limitations and a repeatable release process.
