# Testing

Run from the repository root: `python -m unittest discover -s tests`.
The inherited baseline has 214 tests. Optional Guardrails tests require `requirements-guardrails.txt`.

| Change | Useful test area |
| --- | --- |
| Dialogue, control, wait feedback | `test_service.py` |
| Gemini retry, cooldown, sticky selection | `test_gemini_fallback.py` |
| Provider settings and credential boundaries | `test_llm_settings.py` (see available files) |
| Safeguards | `test_safeguards.py`, `test_guardrails_ai.py` |
| Module preparation and installer | `test_addon.py`, `test_installer.py` |
| Shops | `test_merchants.py` and merchant-related tests |

Use mocked provider responses and temporary directories for regression tests. Never require a real
API key in CI. Exercise failures, stale acknowledgements and cancellation rather than only happy paths.

`tests/live_*.py` harnesses require native files and an isolated game world. They are not included in
unittest discovery and must not be run against production data. A release also needs a real player/DM
playtest: targeting, takeover, persistent placement, store purchases and haggling, lore updates,
restart recovery, failed providers, and a fresh installation by following the written guide.

The source-organization milestone moves method bodies without intended behavior changes. Formatting
uses Black's AST equivalence checks. Preserve the existing tests to detect accidental behavior changes.
