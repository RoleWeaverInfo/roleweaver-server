# Optional demo playtest

Use a disposable local character. Tests are optional; report failures as well as successes.
Start with an online provider that passes the dashboard connection test. Keep near the NPC and use
Talk To/Speak to establish the conversation. Wait for each reply before sending another line.

| Test | What to do | Expected result |
| --- | --- | --- |
| Basic conversation | Ask Mira about the Lantern Rest | A short in-character response |
| Natural follow-up | Ask “How long have you worked here?” without repeating her name | Conversation stays with Mira; unsupported history is not invented as canon |
| Player name privacy | Before introducing yourself, ask “What is my name?” | NPC does not obtain the character name from a nameplate |
| Memory | Introduce yourself as Talen and say you dislike rain; reconnect and ask what you said | Same character's prior conversation can be recalled |
| Character distinction | Ask Mira, Orren and Elara about the closed bridge | Shared facts agree; their voices differ |
| Lore change | Change the bridge fact in World Lore, save, then ask again | New replies reflect the updated fact |
| Lore uncertainty | Ask the exact date the bridge will reopen | They admit no date is known |
| DM control | Log in as DM and possess an NPC; release and resume as needed | AI does not speak over DM control; dashboard state confirms changes |
| Merchant stock | Ask Orren to show his shop and quote an item | Quoted stock/price agrees with the game |
| Purchase | Buy an item, then ask about remaining stock | Game inventory and later quotes reflect the purchase |
| Haggling | Request a modest discount | The game's roll/rules determine the result; compare the reopened shop price |
| Waiting feedback | Observe a naturally slow request | Thinking at about 5 seconds; Hmm after another 10 seconds, then every 10 seconds |
| Failure | Select an unavailable test model, then restore the working one | Errors are visible; failure feedback does not invent an answer |
| Persistent spawn | As DM, spawn a new persistent profile; stop/start the demo | Placement and memory return subject to configured persistence rules |
| Backup | Export a dashboard backup and inspect its reported contents | Backup succeeds; keep it private and test restore only in a disposable instance |

NPC feedback is processed on game ticks, so timing is approximate. Do not manufacture repeated provider
failures against a public service. A missing reply can be a hearing/targeting issue, deliberate policy
block, quota, network failure or malformed output: record which the diagnostics show.

For controlled movement, use the dashboard to capture a walkable destination at the DM, grant Orren
permission to lead there, then ask as a player. The demo does not guess destinations in a replacement map.

For guardrail and LLM quality evaluation, use [LLM_COMPARISON.md](LLM_COMPARISON.md).
