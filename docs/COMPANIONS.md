# Familiar prototype

This is an opt-in development prototype for **standard wizard/sorcerer familiars**.
It adds chat and remembered personality to the creature the game already summoned.
It does not spawn a replacement, change its faction or stats, remove its normal
dialogue menu, or replace heartbeat and combat scripts. Animal companions and
spell summons are future adapters, not supported by this first version.

## Install on a test server

1. Back up the module and Role Weaver databases.
2. Update the Role Weaver Python service and rebuild/install the bridge using the
   normal add-on preparation procedure. The bundle now includes `rw_companion.nss`,
   the `rw_cp_*` includes and entry scripts (`rw_cp_order`, `rw_cp_event`,
   `rw_cp_trade`, `rw_cp_save`, `rw_cp_menu_evt`), plus updated `rw_init`, `rw_tick`, `rw_chat` and
   `rw_modulechat`. Install the complete generated scripts/compiled bundle, not
   just the new entry scripts. Keep the world's existing hooks and handlers.
3. In the instance's `config.json` add `"companions_enabled": true` (with the
   necessary comma between JSON settings). It defaults to false.
4. Restart the Role Weaver service and restart NWN to load the compiled bridge.

Setting `companions_enabled` back to false and restarting Role Weaver disables
the feature. The game's familiar commands remain available.

## Player walkthrough

Use the **Talk chat channel**, not the debug console or a tell.

1. Summon a familiar normally and stand near it.
2. Type `/rw companion on`.
3. Address your familiar in ordinary Talk, such as `Whiskers: Hello!` (use its name).
4. Continue with ordinary nearby Talk: `How are you?` or `What can you see?`.
   You do not need to repeat its name. `Hello Whiskers` and an unambiguous short
   name also open a conversation. Say `bye` or use `/rw end` to finish.
5. Try `/rw companion follow me`, then `/rw companion stay here`. These short
   commands use normal associate behavior immediately, without an LLM request.
   Other phrasings can select follow/stay through the AI's validated action list.
6. Use `/rw companion inventory` to have it approach and show the familiar
   satchel alongside your inventory. Select an item, then **Confirm transfer**.
   You can give, take back, or exchange items without waiting for the LLM.
7. In chat, try `What are you carrying?`, `Pick up that potion`, or `Fetch that
   dagger and bring it to me`. It can also deliver a named satchel item to a
   nearby player or an AI NPC whose item permissions allow receiving it.
8. Try `Whiskers, ask Mira about the bridge, then come back and tell me what she said`.
   Use a nearby, willing AI NPC's name. To allow a longer visit, say `Stay and chat
   for a bit, then report back` (up to three short exchanges).
9. Use `/rw companion off` to stop AI conversation. This does not dismiss the familiar.

For an in-game control panel, type `/rw companion settings` (or `/rw companion menu`).
Opening the menu and changing settings do not call the LLM or require dashboard access.

Responses and command emotes now appear in **normal nearby chat under the familiar's name**.
The player's addressed Talk also remains visible. Nearby players can hear both sides;
only the owner can issue commands. `/rw companion` slash commands and setup notices
stay private. The slash helper can still send a message, but its reply is public.
There is no microphone input or ambient listening in this prototype. The normal
right-click menu and click-to-talk conversation remain available. Combat, death,
possession, distance beyond the configured hearing range (normally ten metres),
and blocked line of sight prevent AI replies.

The profile is keyed to the server world, the existing character identity scheme,
and familiar type, not its temporary object ID or current level blueprint. It
survives dismissal and resummoning. Opt-in lasts for the current player login;
after reconnecting, type `/rw companion on` again. Profiles appear in the dashboard
with a `cp_` stable ID and role **Player-owned magical familiar**. Edit personality,
voice and curated memories there. They will appear unconnected in the ordinary
world-NPC status display: do not use Spawn at DM to create them as world NPCs.
Familiar profiles and conversation histories are included in existing backups.
No familiar placements are saved or restored.

## In-game settings

The familiar settings window provides these player controls:

| Control | Effect |
| --- | --- |
| AI on/off | Enable or disable AI for this login. Opening the menu does not enable it. |
| Reply length | Brief, natural or detailed replies, with a corresponding maximum length. |
| Tone | Character default, warm, playful, reserved or serious. This changes delivery without replacing the DM's character profile, memories or lore. |
| Follow-up conversation | Allow nearby Talk without repeating the familiar's name after addressing it. |
| AI movement | Allow Role Weaver follow/stay commands, item errands and conversation visits. Native game commands and combat remain available. |
| Satchel exchanges | Allow the normal familiar inventory exchange window. |
| Collect/fetch | Allow eligible pickups and approved-container errands; also requires movement and satchel exchanges. |
| Give/barter with others | Allow delivery or barter with eligible nearby recipients; also requires movement and satchel exchanges. Other players still confirm receipt. |

Buttons also provide **Follow me**, **Stand ground**, **Open inventory**,
**Recover satchel items**, **End conversation**, **Cancel current errand**,
**Refresh**, and **Reset preferences**. `/rw companion cancel` cancels an errand
directly. If AI movement is off, stand close to the familiar before opening its
inventory. Recovery remains available even when the familiar or AI is unavailable.

Player choices can restrict server permissions; they cannot grant actions the
server has disabled. Changing preferences cancels pending familiar work. Controls
wait for the service to confirm loading or saving settings before accepting more
changes or AI work. Reopen the menu after changing familiar, resummoning, or its
ten-minute window timeout.

Preferences are saved in the Role Weaver database for this world, character
identity and familiar type. They survive reconnects, resummoning and restarts,
and are included in database recovery snapshots and portable backups (format 13).
Older portable backups use default preferences. The character identity follows
the existing public-CD-key and character-name scheme, so renaming a character
changes its identity. Preference records use a hashed ID, and the raw identity
is not sent to the model. Resetting preferences does not erase memories or items.
AI opt-in is separate: enable it again after each login.

## Follow-up conversation and awareness

A name address or `/rw companion <message>` focuses your conversation on your
familiar. Unaddressed follow-ups use the server's close conversation range
(normally six metres). Focus expires after the configured conversation timeout
(normally three minutes without a new message). Explicitly addressing another
NPC/player, selecting a world NPC with Speak, saying goodbye, or `/rw end` ends
that focus and cancels a pending familiar reply. Unknown colon addresses also end
it; ordinary clauses such as `Yes, thank you` continue the conversation. When two
nearby characters share a name, use `/rw companion <message>` to avoid ambiguity.

Focus also ends on area changes, dismissal, possession, combat, opening a native dialogue, changed native
orders, or loss of hearing range/line of sight. Address the familiar again to
resume. Tells, party chat, slash commands for other features, and OOC lines
starting `//` or `((` are not familiar conversation. This is selected conversation,
not ambient listening to everything the player or nearby characters say.

Each AI conversation request includes a fresh, bounded view from the familiar's
position: visible creatures, doors, containers and fixtures; approximate distance
and direction; visible injuries, fighting, and open/closed state. Walls and
visibility checks exclude unseen creatures/objects. Other player identities,
uninspected container contents, locks, traps, quest secrets and hidden object
identifiers are not supplied. Inventory actions add a separate, limited list of
eligible satchel items, loose items and explicitly approved containers. The
familiar cannot read another player's inventory.

The scan happens when you speak, not as a continuous AI background task. A delayed
observation is marked unavailable instead of refreshed by lifecycle heartbeats.
These observations are not saved as automatic long-term memories. Delivered
conversation still follows the normal history and backup behavior.

## Send your familiar to ask someone

Owner-directed visits let a familiar walk to a visible AI NPC or another player,
ask about a topic, and return to its owner. Examples in nearby Talk:

- `Whiskers, ask Mira what happened to the caravan, then report back to me.`
- `Whiskers, go talk to the innkeeper about the village. Stay and chat for a bit,
  then come back.`
- `Whiskers, ask the traveler ahead whether they saw the caravan.`

The familiar must already be enabled, with **AI movement** on. Visits select
from the creatures visible in its current area, normally within 20 metres.
It walks to the actual creature, rather than a saved location associated with it.
There is no search through other areas. Ambiguous recipient names are withheld;
move closer or identify a uniquely described recipient.

For AI NPCs, the DM must enable **Controlled Actions → Nearby behaviour → Accept
these nearby check-ins** on the recipient. It must be idle in AUTO and outside
an active encounter. Its reply uses its own personality and permitted lore.
The familiar cannot acquire that NPC's actions, private profile or unspoken
knowledge. A brief visit pauses idle patrol scheduling; player conversations
and DM control still take priority.

For another player, the opening question is ordinary nearby chat, not a forced
dialogue menu. A private helper notice explains that their answer will be
reported to the familiar's owner. They can answer in Talk using the familiar's
name (`Whiskers: I saw it heading east.`), use `/rw companion reply <answer>`, or
decline with `/rw companion decline`. The reply helper also speaks the answer
publicly in nearby chat. Ignoring the question causes a timeout; unrelated chat,
tells and private conversation history are never treated as an answer. A visitor
cannot be given movement, inventory or other owner commands by its recipient.

**Ask and report** returns after one answer. **Stay and chat** permits up to
three short exchanges, then returns automatically. Each wait/movement phase has
a 45-second timeout and the conversation has a three-minute overall deadline,
followed by a bounded return/report attempt. The owner must remain in the same
area and within the visit radius plus two metres. Reports quote actual delivered
answers; no reply produces an honest no-answer report. Questions, answers and
the returned report are normal nearby speech.

Use `/rw companion cancel` or **Cancel current errand** to end the visit.
A new message or order from the owner, changed settings, combat, possession,
dismissal or separation also interrupts it. The previous follow/stand-ground
mode is restored when native control permits. Active visits do not resume after
a service/game restart; delivered conversation is retained in normal backups.

### Visit settings for server owners

Visits default to enabled when the companion feature is enabled. They have
their own optional `config.json` policy, independent of inventory permissions:

```json
"companion_visits": {
  "enabled": true,
  "players": true,
  "radius": 20
}
```

Restart Role Weaver after editing it. Set `players` to false to allow AI NPC
recipients only, or `enabled` to false to disable all visits. Radius must be an
integer from 3 to 40 metres; invalid settings disable visits. There are at most
eight offered recipients per request, four active visits admitted by the service,
and two companion model requests at a time. The normal usage panel records these
requests as `companion_visit`. Returning a report does not require another LLM call.

## Familiar satchel and item errands

Enabling your familiar prepares a **Familiar Satchel** in your character's
inventory. It is an ordinary storage bag with no magical item properties, bound
to this world, character and familiar type. The familiar physically walks to
collect or deliver items; its working inventory is this satchel. The familiar's
native equipment remains separate. Satchel weight counts against the owner and
native inventory space limits apply; this prototype has no creature-specific
carrying limits or new familiar equipment controls.

- Owner exchanges show up to 32 eligible items on each side. Transfers use whole
  stacks. Two-sided swaps require non-stackable items; give stacks one way at a time.
- Another player must accept the specific item offered in a private window.
  They cannot browse the owner's satchel or issue orders to that familiar.
- AI NPC deliveries and barter use the recipient's existing Receive/Exchange
  permissions, item value limit and barter value rules. This does not open a
  merchant store or spend gold.
- Plot, cursed, non-droppable, unidentified, equipped and over-limit items, plus
  bags themselves, are excluded from familiar transfers. A changed selection is
  rejected; refresh the window rather than repeating a stale transfer.
- If the player list is empty, check for loose, identified, unequipped items.
  A character carrying only equipped gear and the familiar satchel has nothing
  eligible to give. Unequip an eligible item or pick up an ordinary potion, then
  refresh. **Recover satchel items** intentionally hides the player's list;
  use **Open inventory** for deposits.
- Pickup and delivery require reaching the visible target. Combat, possession,
  changed ownership, native commands, disabled permissions or an expired errand
  interrupt the task. Collected items stay in the satchel. A full bag, blocked
  path or disappearing target does not create replacement items.
- After an errand the stock adapter resumes the prior follow/stand-ground mode,
  unless another command or game state has taken control.

If a pickup merges into another stack, the familiar keeps it in the satchel
instead of guessing which stack to deliver. Retrieve it through the exchange
window. For another player, identify the nearby traveler by position if the
familiar has not learned their name.

### Server settings

With companions enabled, inventory support defaults to on with a 20-metre errand
radius and a 10,000-gold item-value ceiling. Add this optional configuration to
the instance's `config.json`, then restart Role Weaver:

```json
"companion_inventory": {
  "enabled": true,
  "radius": 20,
  "max_value": 10000,
  "containers": []
}
```

The radius may be 3–40 metres; the value ceiling may be 0–100,000. The owner must
stay in the same area and within the errand radius plus two metres. Normal chat
still uses the world's hearing and close-conversation ranges.

Containers are **not approved by default**. Add up to 30 exact placeable tags to
`containers` to allow a familiar to inspect and fetch from those containers.
Only usable, unlocked, untrapped containers without OnOpen/OnUsed scripts qualify.
First ask it to inspect the container; once it reaches and opens it, ask about
the contents and choose an item. Setting integer local `rw_no_companion` to `1`
on a loose item or container excludes it. No theft, lockpicking or scripted quest
containers are enabled by these settings. Invalid settings disable inventory
actions while leaving familiar chat available.

For the supplied throne-room demo chest, add `"rq_testchest"` to `containers`
and restart the Role Weaver service. This approves that chest only; it does not
require an NWN restart. With AI movement, satchel exchanges and collect/fetch
enabled, stand near the chest and ask the familiar to inspect it. Once it reaches
the chest, ask what is inside, then choose an item to fetch. Other worlds should
use their own approved chest tags.

The default bag blueprint is `nw_it_contain001`; a PW can set module string local
`rw_cp_pack_resref` to a suitable **empty** inventory-bag blueprint. Newly created
satchels are plot/non-droppable. Existing native bag access remains available.

### Dismissal, saves and recovery

The one real satchel stays on the character when the familiar is dismissed,
killed or resummoned, and returns with the character after logout or restart.
Role Weaver requests a native character save after confirmed transfers and native
satchel inventory changes. It does not serialize an additional item copy in its
AI database or recreate contents when a familiar appears.

Use `/rw companion recover` for an owner-only, withdraw-only window without a
living familiar, even when companion AI or inventory actions are disabled. You
can also open the bag in the normal character inventory. Recovery selects the
current familiar type's satchel; older types' bags remain accessible natively.
Ambiguous duplicate satchels require DM attention rather than automatic merging.

**Back up the NWN server vault and world data as well as Role Weaver.** Character
saves reduce loss during familiar lifecycle changes; they do not make two
characters' saves or custom world persistence one atomic crash-proof transaction.
Role Weaver database backups contain profiles and conversation history, not the
native possessions in these bags. Servers with custom character-save rules
should test that integration before enabling the feature for players.

## Scope and limits

- Only the owner can command their familiar. Invited recipients can answer its
  questions, but cannot take control.
- AI actions include follow/stand ground, offered item errands and owner-directed visits.
  Native combat remains native; no new attack permissions are introduced.
- A familiar's initial personality uses its creature blueprint where recognized;
  unknown/custom creatures receive a general loyal-familiar personality.
- Current dialogue context includes the latest 16 messages plus curated memories.
  It does not yet perform automatic long-term memory summarization.
- At most two companion generations run at once, sharing existing provider limits
  and safeguards. Busy requests may be skipped; there is no unbounded chat queue.
- No ambient interjections, unattended gathering, scouting, or newly authorized attacks.
- Visits require an explicit owner request and a willing recipient. They do not
  enable autonomous social visits or conversations with other player familiars.
- Menu commands, ownership changes and possession invalidate pending AI commands.
  A repeated identical radial command may not be distinguishable through NWN's
  last-associate-command value; `/rw companion off` always cancels pending AI work.
- An engine acknowledgement records delivered dialogue. Lost acknowledgements do
  not replay a reply or pretend it was heard.

## Adapting a modified persistent world

`bridge/rw_companion.nss` owns consent and message freshness;
`bridge/rw_cp_base.nss` holds shared identity and eligibility checks.
`RWCPFind` is the lookup seam for future nonstandard companion systems. Keep all
ownership and possession checks when extending it; changing lookup alone does not
make an arbitrary NPC safe to control.

`bridge/rw_cp_order.nss` is the stock command adapter. It uses the shipped associate
state flags and follow action. A server may set the module string local
`rw_companion_adapter` to its own script. The script runs on the familiar with
`rw_cp_order` equal to `companion:follow` or `companion:stay`; it must set
`rw_cp_order_ok` to TRUE only if it accepts the order. The bridge clears these
locals afterwards. The LLM cannot supply a script name or target creature.

Inventory errands and conversation visits additionally use `companion:task_move`,
`companion:task_continue` and `companion:task_end`. The validated destination is
provided in object local `rw_cp_order_target` for movement. The adapter must
preserve the prior movement mode at task start and restore it at task end. An
older custom adapter can refuse these orders while retaining follow/stay support.

`rw_cp_pack` owns native satchel binding and transfer rules; `rw_cp_ui` owns
exchange consent and stale-selection checks; `rw_cp_items` builds offered actions
and runs bounded movement tasks. `rw_cp_save` requests character saves for native
bag changes. `roleweaver/companion_inventory.py` filters model context and policy;
it never moves, saves or recreates native items. No player inventory lists,
object references or arbitrary action targets cross into the model.

`rw_cp_prefs` requests and caches service-confirmed preferences; `rw_cp_menu` and
`rw_cp_menu_evt` implement the owner-only settings window. `companion_preferences.py`
validates finite choices and builds temporary model instructions without editing
the stored NPC profile. Preference requests and replies bind to the owner,
familiar type, game session, service generation and request nonce. Native locals
are only a cache. A service restart or database restore invalidates that cache;
actions wait for fresh settings rather than assuming the old permissions apply.

`roleweaver/companions.py` handles profile identity, provider calls, usage,
safeguards and acknowledged history. It does not use the ordinary world-NPC
action queue or its 32 creature slots. State is bounded to 64 recently observed
companions; profiles share the existing 1,000-profile backup limit.

`bridge/rw_cp_visit.nss` owns visit targets, physical movement, recipient consent,
timeouts and speech acknowledgements. `roleweaver/companion_visits.py` coordinates
short exchanges and reports from the acknowledged speech ledger. Opaque offered
action IDs reach the model; engine object IDs and UUIDs do not. Visit transcripts
are separated from the owner's private conversation. Recipient NPCs receive only
the familiar's actual spoken question and their own lore/memories. The native
reservation used by `RWHasConversation` expires or becomes invalid when its owner
or familiar is unavailable, so a lost visitor cannot permanently stop a patrol.

## Tests before expanding support

Run `python -m unittest tests.test_companions tests.test_companion_inventory tests.test_companion_preferences tests.test_companion_visits` and
the normal regression suite.
Compile `tests/companions_native.nss` as `invtest` in an isolated module/userdata
directory. It checks native protocol rejection and absence of world bindings;
it cannot substitute for testing with a real player familiar.
Also compile/run `tests/companion_inventory_native.nss` in an isolated test
module/userdata directory. It creates temporary items and a campaign save to
verify native transfers, stale selections, owner isolation and saved-bag contents.
`tests/companion_controls_native.nss` checks preference validation, effective
permissions, recovery and stale-cache rejection in the same isolated setup.
`tests/companion_visits_native.nss` checks receiver restrictions, bounded turns,
return/cancellation, orphaned reservations and forged visit commands.
Never install these fixtures as a live module's load script.

With a real wizard/sorcerer, check follow/stay, original menu commands, a slow
response interrupted by possession, dismissal and resummoning, reconnect, area
transitions and combat. Connect a second player to verify owner isolation.
Try follow-up Talk without repeating the name, address another NPC/player, then
check `/rw end`, timeout, walking away and speaking through a wall. Ask what the
familiar sees, move to a different area, and ask again. It should not invent chest
contents or identify an unknown player. Nearby players should hear the familiar's
replies but must not be able to issue commands to someone else's familiar.
Try the server's custom familiar scripts before enabling this on an established PW.

For inventory playtesting:

1. Open `/rw companion inventory`, give it a potion, refresh, and take it back.
   Close/reopen the window and try both stacks and non-stackable items.
2. Drop an ordinary identified item nearby; ask it to collect it, then fetch an
   item and bring it back. Repeat across a wall, with a full bag, and after someone
   else picks up the target. No stale or failed request should duplicate an item.
3. Deliver to a second player: decline once, then accept. Confirm only the chosen
   item moves and the recipient cannot browse or command the familiar.
4. Give/barter with an opted-in AI NPC; then disable its permissions and retry.
5. Interrupt a walk with stand ground, possession or combat. Verify native control
   takes over and any collected cargo remains recoverable.
6. Dismiss, resummon and reconnect with items in the satchel. Restart the test
   server, then verify counts and `/rw companion recover` without a familiar.

For player-control playtesting:

1. Open `/rw companion settings`. Check that the layout fits the window and each
   setting remains visible after saving and reopening.
2. Change reply length and tone, then converse. Confirm the familiar retains its
   identity and the dashboard profile has not been overwritten.
3. Turn follow-ups off, then movement and item permissions off in turn. Confirm
   disallowed commands are unavailable, including a delayed AI reply after a
   setting changes. Cancel an active errand and recover any collected items.
4. Reconnect and resummon. Preferences should remain saved, while AI starts off
   until you opt in. Repeat after a service restart or a database restore.
5. Use a second character to check independent preferences and owner-only access.

For conversation-visit playtesting:

1. Enable a nearby AI NPC's receive check-in permission. Ask the familiar to get
   one answer and return. Check physical arrival, both speakers' chat and the
   report beside the owner. Ask about something only the recipient's lore covers.
2. Ask it to stay and chat. It should finish after no more than three replies.
   Check that the recipient's idle patrol can resume after the visit.
3. Invite a second player: answer by name, then with the reply helper. Decline a
   separate visit, then ignore another. Unrelated Talk and tells must not enter
   the report; the recipient must not be able to command the familiar.
4. Cancel while walking or awaiting a slow model. Repeat with revoked movement
   permission, paused recipient, combat, dismissal, possession and an area change.
   No delayed reply should continue an interrupted conversation.
5. Place a wall between the familiar and recipient, or move the recipient away.
   It must not report a conversation that did not happen or remain stuck forever.

## Next development steps

The settings window is the first step of the companion roadmap. Protection
commands, optional social participation, adapters for other companion types,
equipment and practical assistance, improved following/recovery, and stronger
personal continuity remain future work. The controls above do not enable those
unimplemented behaviors.
