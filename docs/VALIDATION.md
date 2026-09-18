# Source baseline validation

Validated on 2026-09-18 before publishing this source-organization milestone:

- Ubuntu 24.04 / Python 3.12 with optional Guardrails installed: **214 tests passed**.
- Windows core run before formatting: 214 tests completed, 8 optional tests skipped.
- Browser draft recovery and UI checks: passed (`node tests/test_drafts.cjs`).
- Isolated Ubuntu offline dashboard startup and HTTP state/page checks: passed.
- Python formatting used Black 26.3.1 with AST equivalence validation.
- Local Markdown links resolve; source scan found no recognized credential patterns.

The running NWN/demo installation was not changed. No new native compilation or live gameplay test
is claimed for this structural refactor. CI is configured to repeat core/Guardrails and browser tests.
