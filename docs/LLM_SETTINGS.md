# LLM settings — 0.26.0

1. Open **LLM Settings** in the dashboard's left sidebar.
2. Choose **OpenAI**, **Google Gemini**, or **LM Studio (local)**.
3. For a cloud provider, choose **Add or replace key** and paste that provider's API key. The two services have separate keys. Existing environment keys remain usable; you do not have to paste the current OpenAI key again.
4. Click **Fetch models**, then select a text chat model or type its exact model ID. Listings can include non-chat models; not every model works with NPC dialogue and JSON action replies.
5. Click **Test connection**. This sends a small synthetic prompt and checks a JSON reply. It does not send lore or player messages and does not change your active provider. Cloud tests can incur a small charge and appear under Usage & Performance / Connection tests.
6. Click **Save and activate**. New NPC replies and AI safeguard reviews use the selected service. No NWN restart is needed. Pending generations are discarded on a switch.

The original config.json connection stays unchanged until you save. Select **Original config.json connection** to return to it. Offline test mode is also available. Settings survive dashboard restarts. Save each provider before switching away if you want to keep its entered key/model; unsaved keys are never stored in browser draft recovery.

## LM Studio on the same Ubuntu machine
Start LM Studio's local API server, load a chat-capable model, and use `http://127.0.0.1:1234/v1`. If LM Studio authentication is enabled, enter its API token; otherwise leave the key empty.

## LM Studio on your Windows computer
Enable LM Studio's local-network serving. Use your Windows computer's private network address reachable from Ubuntu, for example `http://192.168.167.1:1234/v1` (replace the example with your actual address). Allow the chosen port through the Windows firewall for the VM/trusted local network. `localhost` in this dashboard means the Ubuntu server, not the browser's computer. HTTP sends prompts and tokens without transport encryption: use a trusted private network or an HTTPS endpoint. Private numeric IP addresses and localhost are accepted; arbitrary hostnames/public HTTP addresses are not.

## Keys and backups
Keys are stored in `data/llm-settings.json`, under the runtime data directory, with owner-only permissions (0600 on Ubuntu). This file is not encrypted; protect the Ubuntu account and disk. Keys are never returned by the dashboard API, written to usage logs, or included in Role Weaver recovery backups/distribution packages. Keep your own password-manager copy. Blank **Keep current key** preserves it; **Remove saved key** removes it from these settings and disables environment fallback for that provider. It does not delete an old key from provider.env or revoke it at the provider. Replacing a local server address clears its token unless you explicitly supply a new one. Cloud endpoint addresses are fixed; redirects are refused.

## Limits and monitoring
The response token limit includes reasoning tokens on models that report them; use a sufficient limit for a complete JSON response. Timeout can be increased for slower local inference. Changing providers never silently falls back to a different service. Existing game safeguards and action validation still apply; local models need to follow JSON instructions reliably. A small connection test is not a guarantee of good roleplay or safeguard accuracy: playtest your chosen model.

Token counts and latency use the provider's reported usage. Cost estimates remain owner-entered under Usage & Performance, separated by endpoint/model. Local hardware and electricity costs are not inferred.

Official API references: [OpenAI models](https://developers.openai.com/api/reference/resources/models/methods/list), [OpenAI chat parameters](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), [LM Studio compatibility](https://lmstudio.ai/docs/developer/openai-compat).

## Gemini busy/timeout fallback — 0.26.2
Enable **On Gemini busy or timeout errors, try other free-tier Flash models** for the supported Flash and Flash-Lite models listed below. The selected model is attempted first; HTTP 503, HTTP 408/504, and connection/response timeouts advance through the available fallback models listed below, skipping duplicates. IDs with a `models/` prefix are supported. At most three attempts share the configured request time budget. Each attempt gets the remaining budget divided by the remaining model count (initially about 20 seconds each with a 60-second budget). Unused time is available to later attempts. Socket timeouts and a monotonic deadline bound retries; network read timing may add overhead. Each new dialogue/review request starts with your selected model unless cooling down; settings are never silently changed. The same key and prompt are used, and output checks remain active. Authentication errors, quota errors (429), invalid output and other failures do not trigger fallback. If all attempts fail, normal dialogue error/safeguard behavior applies.

These specific text models have free-tier input/output listed on Google's pricing page, checked September 18, 2026. Actual billing and availability depend on your Google project; Role Weaver cannot detect/enforce a free billing tier. This is not a spending cap. No paid-only models, moving aliases, other providers or alternate keys are selected. Recheck eligibility if Google changes pricing. Usage records each attempt under the actual requested model; estimates use that model's configured rates, not the primary model's rates.


## Expanded fallback and timeout cooldown — 0.26.3
Supports Gemini 3.8/3.7/3.6/3.5 Flash and 3.5/3.1 Flash-Lite. Try the selected model, then available models in order: 3.7, 3.6, 3.5, 3.8 Flash, 3.5 and 3.1 Flash-Lite, skipping duplicates. At most three attempts per request share the existing time budget. Connection/response timeouts and HTTP 408/504 put that model on a two-minute, process-wide cooldown shared by dialogue and safeguard reviews. Other models can be tried by subsequent requests; after cooldown the selected model is eligible again. HTTP 503 still triggers fallback without cooldown. If all six are cooling down, fail promptly through the existing error handling. Cooldowns are held in memory and reset on app restart. Disabling fallback bypasses cooldowns. No keys or player text are stored in cooldown state.

## Gemini structured responses — 0.26.4
Gemini safeguard reviews, controlled-action replies and connection tests explicitly request JSON Schema output. Local validation and guardrail failure handling remain active. Malformed results are never treated as successful reviews. Plain speech and other providers are unchanged.

## Sticky Gemini fallback — 0.26.5
After a successfully decoded response, subsequent dialogue and safeguard requests prefer that working model until it fails, even after another model's cooldown expires. Preferences are scoped to selected model and a one-way credential fingerprint; no keys are stored in this state. App restart clears preferences. Retry eligibility, three-attempt budget, timeout cooldowns and strict validation remain unchanged. Invalid responses clear the preference but do not retry a safeguard verdict.
