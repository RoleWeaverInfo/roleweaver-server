# Dialogue safeguards — Role Weaver 0.16.0

Open **World administration → Guardrails**. Changes are saved in the Role Weaver database, survive restarts and are included in version 5 recovery/manual backups. Older backups remain supported and leave current safeguard settings unchanged.

## Basic controls

- **Content sensitivity:** Off, Low, Medium or High independently for profanity, hate speech, violence and owner-defined sensitive topics. Low flags estimated severity >= 0.90, Medium >= 0.65, High >= 0.35. These scores are AI estimates, not calibrated probabilities. Higher violence sensitivity may reject ordinary fantasy combat.
- **Action:** Log only permits flagged dialogue; Fallback substitutes an in-character response; Block keeps the NPC silent for that turn. Every flag records a category and action. Blocking affects Role Weaver, not the player's original NWN chat. Rejected incoming dialogue is replaced with a placeholder in Role Weaver history to avoid replaying it later.
- **Catch lore mistakes:** Reviews factual claims in an NPC answer against its own lore, shared World Lore, authorized Lore Access entries and DM-curated memories. Paste source documents into those existing fields. DM-only and other NPCs' private lore are excluded; player claims and conversation history are not canonical source documents. Both contradictions and unsupported invented facts are flagged. Greetings, opinions and ordinary roleplay gestures do not require sources.
- **Protect privacy:** Independent switches for card numbers, phone numbers and street addresses. Local patterns/checksums mask new incoming dialogue before Role Weaver stores it, outgoing replies before shortening them for NWN, and older context/profile/memory text before sending it to the provider. This is custom local format recognition, not the Guardrails Hub PII model. It recognizes Luhn-valid 13–19 digit cards, common formatted phone numbers (or labeled bare numbers), and numbered English street-address formats. It may miss unusual/international formats or match fictional addresses. It does not erase old records/backups, mask character identity fields, or alter NWN chat/logs.

Privacy masking starts enabled. Optional content and lore reviews start **Off**. Existing prompt-injection checks remain enforced regardless of Log only. New settings cancel older in-progress replies. The latest 20 policy/privacy events are shown, with at most 200 stored; the event log contains categories/actions, not dialogue, detected private data or account IDs.

## Requests and limitations

The optional AI reviewer uses the same configured provider/model as NPC dialogue. Content review adds up to two requests per turn (incoming and outgoing); lore-only review adds one. If both are enabled, lore shares the outgoing review. This increases token usage and response time. There are no retries or new third-party validation services. Local masking and the existing deterministic checks add no LLM requests.

The review returns a strict structured verdict; Guardrails AI's custom owner-policy validator applies sensitivity thresholds. Timeout, invalid output, unavailable SDK/provider or over 60,000 characters of serialized review data blocks the affected turn rather than guessing or silently dropping sources. The per-player/server dialogue limits and four concurrent workers still apply. A dialogue turn may now contain up to three provider requests in total.

AI review can miss mistakes, misclassify roleplay and be manipulated; it is not proof that every answer is correct or safe. Do not put information that must never be disclosed into an NPC's authorized knowledge. Use DM-only lore for absolute separation from AI prompts.

## Installation

The development VM already has Guardrails AI 0.11.0 enabled. Refresh the dashboard. Only the app service needs restarting:

```bash
systemctl --user restart roleweaver-easy-app
```

For another installation, from the extracted package folder:

```bash
python3 -m venv .venv-guardrails
.venv-guardrails/bin/python -m pip install -r requirements-guardrails.txt
```

If Ubuntu reports venv is unavailable, install `python3-venv`. Add `"guardrails_ai": true` to your existing JSON configuration, keeping its other settings. Use `.venv-guardrails/bin/python` instead of `python3` in the app service's ExecStart, preserving its working directory, environment file and configuration path. Run `systemctl --user daemon-reload` and restart that app service. Check Overview for the active SDK status.

The core SDK and official RegexMatch 0.1.0 run locally with telemetry disabled, per-thread guards and cleared SDK histories. The custom owner-policy validator evaluates structured review scores locally; the optional scoring/lore assessment itself runs at your configured provider. No Guardrails account is required. Dependencies remain isolated from system Python; no Docker is needed.

Tests: `.venv-guardrails/bin/python -m unittest discover -s tests`.
