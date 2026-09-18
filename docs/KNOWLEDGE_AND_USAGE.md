# Knowledge and Usage & Performance — 0.18.0

## Inspect what an NPC can know

1. Refresh the dashboard and select **Knowledge** in the left sidebar.
2. Choose an NPC. Inspect its personal lore, role, personality, voice, boundaries and DM guidance.
3. World documents and Lore Access entries show Included/Excluded. Excluded entries show their title and reason; their text is not presented as NPC knowledge. The same audience filtering used for generation determines access, including active state, public/NPC/faction permissions and DM-only exclusion.
4. Choose a player reference to inspect personal memories and their latest conversation. References are hashed identifiers, not names made available to the AI.
5. Expand a source to read it or use the search box. Edit source documents in World Lore/Lore Access or the profile in NPCs.
6. Use **Edit** or **Forget** on a curated memory to correct it. Corrections invalidate in-flight generation, and memories remain in the ordinary gameplay backups. Forgetting one memory does not erase related history, other lore, earlier replies or old backups.

The view shows saved source context, not model thoughts or proof the NPC will accurately recall every fact. Recent player statements remain unverified claims. It shows the newest 30 applicable curated memories and up to 16 recent messages, matching generation's current selection limits. Shared-only view has no player transcript. Historical name protection, PII masking and dialogue safeguards still run when requests are made, so this is not an exact wire-prompt viewer. Knowledge inspection does not make an LLM request. Refresh it after changes; navigation preserves open edits, and refreshing/changing selection warns before discarding edited memory text.

## Monitor requests

Select **Usage & Performance**. Choose the last hour, 24 hours, 7 days or 30 days, and optionally filter by NPC, model and request category.

- Actual provider HTTP attempts, errors and error rate.
- Provider-reported input/output tokens, plus cached-input and reasoning subsets when reported. Reasoning is not added twice to output totals.
- JSON request size in bytes and message-content characters. Bytes include JSON formatting/escaping, not HTTP headers. This is not an approximate tokenizer.
- Complete provider-request duration in seconds, average and nearest-rank 95th percentile. Includes network time, excludes queue/game delivery and other requests in the same turn. This is not time-to-first-token (requests are not streamed).
- USD estimates with coverage counts: missing usage or rates mean unknown, never zero. Errors may still have reported, billable tokens; those are counted.
- Five graphs: reported tokens, request/error counts, provider latency, estimated cost and request size. Hover over points for values. Tables give breakdowns and the latest 50 matching attempts.

Dialogue, input safeguard reviews and output safeguard reviews are counted separately, including requests whose eventual NPC reply is blocked or discarded. Offline replies, rejected requests before transport, local privacy checks and local guardrails do not make provider calls and are not counted. Monitoring itself makes no additional LLM requests.

## Prices

Expand **Model pricing** and enter your exact model's USD input/output/cached-input rates per million tokens. Rates are scoped to the configured provider endpoint and model. The optional input-token ceiling suppresses estimates above the range to which those rates apply. Blank cached rate uses the normal input rate; unreported cache hits are estimated as ordinary input.

Rates are captured when each request begins. Changing them affects future requests only, not old estimates. Other tiers, long-context/cache-write surcharges, tools, taxes, credits and discounts are not included. Compare against your provider's invoice for actual charges.

For the current Ubuntu deployment, OpenAI's gpt-5.6-luna model page was checked on 2026-09-17: standard input $0.20, cached input $0.02, output $1.20 per million tokens. The initial ceiling is 272,000 input tokens, above which the page lists different pricing. These initial rates will be entered only if this exact OpenAI endpoint/model has no saved rates; other models remain unpriced until configured. Source: https://developers.openai.com/api/docs/models/gpt-5.6-luna . Always review rates if your provider or service tier changes.

## Storage and privacy

Tracking starts with this release; older activity cannot be reconstructed. Up to 30 days or 50,000 request records are retained, whichever limit is reached first. The charts cover retained records only. The earliest retained timestamp and pricing/token coverage are shown.

Metadata is stored in a separate local `data/usage.sqlite3` SQLite WAL database, including price snapshots. It survives dashboard restarts and is not rewritten by restoring gameplay backups. Existing dashboard recovery exports contain gameplay knowledge, not usage records or rate settings. Back up this database separately if long-term usage history is required (use SQLite's backup API, or stop the dashboard before copying it).

No request prompts, reply bodies, credentials, player references or source texts are retained in telemetry. Error records contain exception class/HTTP status only. Knowledge views remain part of the existing localhost administrative dashboard; do not publish that dashboard as a player-facing endpoint.

## Validation

Automated tests cover reporting, provider success/failure accounting, missing counts, cached/reasoning tokens, concurrent writes, time/filter aggregation, pricing snapshots, player isolation, lore access, memory editing and all three service request categories. Browser testing uses isolated synthetic fixtures; no real player dialogue is sent to an LLM as a test. This release changes Python and dashboard files only; no NWN script recompilation or game restart is needed.
