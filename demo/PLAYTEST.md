# Optional demo playtest

For DM tests, start the NWN DM client (`-dmc`) and use the game port with password `roleweaver` on a newly prepared demo. For an older instance, follow the password reset instructions in START_HERE.md.

Use a disposable local character. Tests are optional; report failures as well as successes.
For the forest robbery and troll hostage scenes, see [ENCOUNTER_AREAS.md](ENCOUNTER_AREAS.md).
The **Royal Guide**, beside the hall entrance, offers an optional in-game walkthrough
of conversations, shopping, NPC actions, both encounters and translation. Choose
Talk To, pick any topic, and return to the menu or leave whenever you like. His
ordinary dialogue is also a translation example. The walkthrough contains no
Guardrails testing prompts; model evaluation remains an optional separate document.
Start with an online provider that passes the dashboard connection test. Keep near the NPC and use
Talk To/Speak to establish the conversation. Wait for each reply before sending another line.

| Test | What to do | Expected result |
| --- | --- | --- |
| Basic conversation | Ask the Tavern Owner about life in Crownbridge | A short in-character response |
| Natural follow-up | Ask “How long have you worked here?” without repeating his name | Conversation stays with the Tavern Owner; unsupported history is not invented as canon |
| Player name privacy | Before introducing yourself, ask “What is my name?” | NPC does not obtain the character name from a nameplate |
| Memory | Introduce yourself as Talen and say you dislike rain; reconnect and ask what you said | Same character's prior conversation can be recalled |
| Character distinction | Ask the Tavern Owner, the Merchant and Aldren about life in the kingdom | Shared facts agree; their voices differ |
| Lore change | Add a temporary public festival fact in World Lore, save, then ask again | New replies reflect the updated fact |
| Lore uncertainty | Ask for an unspecified festival date | They admit no date is known |
| Investigation | Ask the guard for your assignment, collect two witness accounts, request the King and explain your suspect | Native story checks confirm evidence and reward a correct verdict |
| New visit | Reconnect after progressing the case | Case progress resets; personal conversation memories remain |
| DM control | Log in as DM and possess an NPC; release and resume as needed | AI does not speak over DM control; dashboard state confirms changes |
| Merchant stock | Ask the Merchant to show his shop and quote an item | Quoted stock/price agrees with the game |
| Purchase | Buy an item, then ask about remaining stock | Game inventory and later quotes reflect the purchase |
| Haggling | Request a modest discount | The game's roll/rules determine the result; compare the reopened shop price |
| Waiting feedback | Observe a naturally slow request | Thinking at about 5 seconds; Hmm after another 10 seconds, then every 10 seconds |
| Failure | Select an unavailable test model, then restore the working one | Errors are visible; failure feedback does not invent an answer |
| Persistent spawn | As DM, spawn a new persistent profile; stop/start the demo | Placement and memory return subject to configured persistence rules |
| Backup | Export a dashboard backup and inspect its reported contents | Backup succeeds; keep it private and test restore only in a disposable instance |
| Familiar creature awareness | Summon and enable a familiar, enter the cave, then ask what it sees | Visible trolls can be described as trolls; hidden intentions are not invented |
| Familiar local listening | Enable Local listening in `/rw companion settings` before entering the cave. After nearby demands/pleas, ask what is happening | The familiar can refer to recently heard public speech, without automatic replies or action orders from bystanders |
| Listening privacy and reset | With another tester, send a tell or whisper, then turn listening off or leave the area | Private text is not supplied; the short listening buffer clears. Existing conversation memories remain |

NPC feedback is processed on game ticks, so timing is approximate. Do not manufacture repeated provider
failures against a public service. A missing reply can be a hearing/targeting issue, deliberate policy
block, quota, network failure or malformed output: record which the diagnostics show.

For controlled movement, use the dashboard to capture a walkable destination at the DM, grant the Merchant
permission to lead there, then ask as a player. The demo does not guess destinations in a replacement map.

Administrator model-evaluation notes are separate from this gameplay walkthrough.

## Try an AI familiar

Use a wizard or sorcerer who can summon a familiar. Companion AI is enabled by
default in new demos; older instances keep their saved setting in the dashboard's
**Companions** panel. Summon normally, then use
`/rw companion on` and `/rw companion settings` in Talk.

Address it by name, introduce yourself, then continue nearby conversation. Ask it
what it can see, to follow/stay, or to visit a nearby AI NPC and ask a question.
Use `/rw companion inventory` to see its satchel and eligible exchanges. Actions
depend on the player's settings and server permissions; inventories and combat
remain governed by the game. Dismiss and resummon the same type to check continuity.

The DM can edit **Familiar starting templates** before a new profile's first AI
chat. Existing companions keep their own profiles and memories. See
[Companions](../docs/COMPANIONS.md) for permissions and current type limits.

## Encounter checks

Captain Beran patrols the hall, pausing when a player speaks to him. In the cave,
Elana and the trolls have brief exchanges while a player is present. Allow a few
seconds between replies; player conversations take priority.

Agree to Morga's ransom or Rusk's toll to open a payment offer. Approach within
3 metres before confirming payment; no gold moves without confirmation.
Item exchange is also available, but an item gift does not automatically pay
the ransom. To try combat, refuse the demand, wait for the explicit warning and
five-second grace, then repeat the refusal or threaten to fight while remaining
nearby. Silence, ordinary questions, and walking away do not trigger combat.
