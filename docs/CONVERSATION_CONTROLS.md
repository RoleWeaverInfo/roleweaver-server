# Conversation & Hearing — 0.21.0

1. Open **Conversation & Hearing** in the dashboard sidebar.
2. Set **Initial Talk To distance** (default 3 metres), **Ongoing conversation distance** (6 metres), **Hearing range** (10 metres), and **Inactivity timeout** (180 seconds).
3. Choose whether to keep conversations while following NPCs, require line of sight, and allow direct addressing to start conversations. All three default to enabled.
4. **Save and apply**, then wait for the game-confirmed values. Changed rules clear existing targets; players select or address their NPC once again.

Ranges accept whole metres from 1–20, with initial distance <= ongoing distance <= hearing distance. Timeout accepts 15–300 seconds. **Fill defaults** only changes the form until saved.

Following keeps the selected NPC within hearing range, even when the player briefly falls behind the ordinary conversation distance. Follow-up speech uses hearing range while the NPC is walking and for 10 seconds after it stops; otherwise it uses ongoing distance. A player can catch up and resume without repeating a name. Timeout, same-area, line-of-sight, life and control checks still apply. Following does not move players automatically.

Full names, unique first names and stable IDs can address an NPC. Common leading titles are skipped when deriving a short name (Captain Beran becomes Beran). Ambiguity requires Talk To or a unique full name/ID. Ordinary comma phrases no longer end the conversation. Recognized addresses to other characters and explicit colon addresses still switch or end the old target. See [CONVERSATIONS.md](CONVERSATIONS.md).

With direct-address starts disabled, use Talk To to begin. Addressing the selected NPC remains available within hearing range while the target remains valid. **End active conversations** clears every target and invalidates old pending replies once the game confirms; it does not pause NPCs or erase lore/memories. Identical saves do not reset targets.

These settings route AI dialogue, not NWN broadcast distances. Replies remain public. Party chat, tells, DM speech and OOC prefixes are excluded. Inactivity is measured from relevant player speech/selection, not NPC replies.

## Persistence and upgrading

Settings are included in backup format 8, along with the existing lore, NPC, memory and action data. Formats 1–7 remain readable. Legacy conversation rules retain their custom distances and timeouts: their old close range becomes both initial and ongoing distance, with following disabled. Backups without conversation rules preserve the current rules. New installations use the new defaults.

The updated bridge reports conversation protocol 2. Older scripts are shown as requiring an upgrade, never as confirmed. Install all rebuilt bridge scripts and restart the game once. Later changes apply without restarting. On the existing development server this release applies the requested 3-metre selection, 6-metre ongoing range, 180-second timeout and following enabled, preserving the current hearing range and other switches.

The dashboard distinguishes pending, applied, offline and upgrade-required. Commands are scoped to world, game session, expiry and policy revision. Saving offline is allowed; reconnect synchronizes settings. Existing dialogue wrappers and restoration on unbind remain preserved.
