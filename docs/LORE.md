# Lore management — 0.5.0

Refresh http://127.0.0.1:8742. The Shared world lore editor appears above the NPC profile. Save public setting facts here; every NPC receives them on new replies. Limit: 20,000 characters. Save an empty field to clear it. Lore persists in this companion installation's SQLite database independently of NPC deletion and restart.

Use NPC-specific knowledge in the selected profile for facts only that character knows. Use Limits and secrets for disclosure instructions. Knowledge isolation prevents another NPC's profile from entering the prompt; disclosure instructions for knowledge the model receives are behavioral instructions, not an access-control guarantee. Do not put DM-only information that no NPC should know into shared lore.

Existing per-NPC curated memories and per-player conversation histories are unchanged. Shared lore is not propagated to other world installations. Saving changes cancels generation still in progress; already queued or spoken replies and remembered transcripts are not rewritten.

Test: add a public fact, ask Mira and Orren about it, then place a different fact only in Mira's NPC-specific knowledge and ask both. Restart persistence, clearing, input limits, context isolation and in-progress cancellation are covered by the 36 passing Python tests. Actual AI roleplay remains a player acceptance check. No fictional setting facts were added automatically.
