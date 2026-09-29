# Alpha 0.3.0 release review

Reviewed and packaged **2026-09-29**. Distribution **0.3.0**, runtime **0.28.0**.
This is a local packaging record, not a claim that GitHub publication or a clean
installation rehearsal has occurred. Source changes remain available for review
before committing/tagging.

## Corrections made during review

- Demo builds were using older bridge scripts embedded in the module. The builder
  now refreshes managed bridge scripts and assets from this package before
  compiling. Both archives contain the same refreshed example module. Existing
  area layout, placements, module event assignments and investigation source
  hooks were verified unchanged.
- The generic module-copy builder was missing the health and native translation
  includes. Both include lists now contain them; a dependency-closure check covers
  prepared Role Weaver includes.
- Several translation tools and tests depended on the demo's GFF helper. They now
  use the shared tools helper, so the add-on archive can import and use them
  independently of the demo download.
- Package selection now rejects runtime data, credentials, unexpected modules
  and unreviewed binary formats. Native server/plugin/compiler binaries remain
  external. Archives use stable metadata and include versions, notes and hashes.
- Archive inspection caught Windows line endings in the optional new-server
  launcher. Packaging now normalizes reviewed text to Linux line endings while
  leaving binary world/assets untouched.
- Updated version labels, upgrade instructions, documentation links, support
  reporting and the roadmap for the larger demo/developer work before 1.0.

## Completed checks

| Check | Result |
| --- | --- |
| Focused Python release tests on Ubuntu | 62 passed, none skipped |
| Same focused tests on Windows | 59 passed, 3 Linux-only skips |
| Extracted add-on source imports | All shipped Python test modules import; setup, dialogue preparation and guide tools accept `--help` |
| Native example module compilation | 35 entry scripts compiled against the existing Ubuntu NWN/NWNX dependencies |
| Existing-server bridge compilation | 24 entry scripts compiled against the same dependencies |
| Authored example resources | 18 non-script resources retained byte-for-byte; story source hooks preserved |
| Python formatting | Black check passed across 131 Python source files |
| Dashboard JavaScript | Syntax checks and existing draft-recovery tests passed |
| Linux shell launchers | `bash -n` passed; packaged launchers use LF line endings |
| Distribution boundaries | Separate demo/add-on contents, module equality, manifests, executable modes, deterministic rebuilds and exclusion checks passed |

The focused suites cover distributions, demo building, integration preparation,
translation surfaces, health, translation diagnostics, guided setup and recovery
HTTP routing. They use fixtures/mocks for provider calls and recovery scenarios.
They did not interrupt the live server or simulate a real crash. Native
compilation used isolated staging output; no game server was started, stopped or
reconfigured for this review.

Earlier in-game feedback includes two simultaneous players viewing German and
Spanish dialogue privately while public spoken text remained English. That is
prior playtest evidence, not a new multiplayer run of the final archives.

## Open checks and release limits

- Review the inherited creature blueprint and supplied module's third-party
  content provenance/redistribution permissions. Details remain in
  [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Clean-install/upgrade rehearsals, real interruption/recovery exercises,
  additional multiplayer scenarios and extended runs remain deferred at the
  project owner's request. Do not describe them as passed.
- The optional translation adapter remains specific to Linux x86-64 NWN/NWNX
  8193.37-17 with matching headers/Core; other native builds are not validated.
- Commit/push, tag creation and GitHub asset upload are separate actions.

See [release notes](alpha-0.3.0.md) for user-facing changes and limitations, and
[packaging](../DISTRIBUTIONS.md) for archive verification/publication steps.
