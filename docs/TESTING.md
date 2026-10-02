# Testing

Run from the repository root: `python -m unittest discover -s tests`.
Optional Guardrails tests require `requirements-guardrails.txt`.

| Change | Useful test area |
| --- | --- |
| Dialogue, control, wait feedback | `test_service.py` |
| Gemini retry, cooldown, sticky selection | `test_gemini_fallback.py` |
| Provider settings and credential boundaries | `test_llm_settings.py` (see available files) |
| Safeguards | `test_safeguards.py`, `test_guardrails_ai.py` |
| HTTP admission, malformed requests and AI/provider overload recovery | `test_http_security.py`, `test_recovery_http.py`, `test_resource_limits.py` |
| Dashboard login, reset/revocation, private recovery and server probes | `test_dashboard_auth.py`, `test_recovery_http.py` |
| Module preparation and installer | `test_addon.py`, `test_installer.py` |
| Shops | `test_merchants.py` and merchant-related tests |
| Database integrity, retention and interrupted restore | `test_database_recovery.py`, `test_recovery_http.py` |
| Translation isolation, stale results and on-demand dialogue preparation | `test_translation.py`, `test_translation_surfaces.py`, `test_prepare_dialogues.py` |

Use mocked provider responses and temporary directories for regression tests. Never require a real
API key in CI. Exercise failures, stale acknowledgements and cancellation rather than only happy paths.

`tests/live_*.py` harnesses require native files and an isolated game world. They are not included in
unittest discovery and must not be run against production data. A release also needs a real player/DM
playtest: targeting, takeover, persistent placement, store purchases and haggling, lore updates,
restart recovery, failed providers, and a fresh installation by following the written guide.

Run `node tests/test_drafts.cjs` and `node tests/test_companion_templates.cjs`
for browser draft recovery. Release checks also verify documentation links, clean
seed data, distribution boundaries and checksums; see [the review record](releases/1.0.0-review.md).
