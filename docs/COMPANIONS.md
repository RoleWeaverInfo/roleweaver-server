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
   `rw_cp_trade`, `rw_cp_save`), plus updated `rw_init`, `rw_tick`, `rw_chat` and
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
8. Use `/rw companion off` to stop AI conversation. This does not dismiss the familiar.

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

- Only the owner can address or command their own familiar through this layer.
- AI actions include follow/stand ground and the currently offered item errands.
  Native combat remains native; no new attack permissions are introduced.
- A familiar's initial personality uses its creature blueprint where recognized;
  unknown/custom creatures receive a general loyal-familiar personality.
- Current dialogue context includes the latest 16 messages plus curated memories.
  It does not yet perform automatic long-term memory summarization.
- At most two companion generations run at once, sharing existing provider limits
  and safeguards. Busy requests may be skipped; there is no unbounded chat queue.
- No ambient interjections, unattended gathering, scouting, or newly authorized attacks.
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

Inventory errands additionally use `companion:task_move`,
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

`roleweaver/companions.py` handles profile identity, provider calls, usage,
safeguards and acknowledged history. It does not use the ordinary world-NPC
action queue or its 32 creature slots. State is bounded to 64 recently observed
companions; profiles share the existing 1,000-profile backup limit.

## Tests before expanding support

Run `python -m unittest tests.test_companions tests.test_companion_inventory` and
the normal regression suite.
Compile `tests/companions_native.nss` as `invtest` in an isolated module/userdata
directory. It checks native protocol rejection and absence of world bindings;
it cannot substitute for testing with a real player familiar.
Also compile/run `tests/companion_inventory_native.nss` in an isolated test
module/userdata directory. It creates temporary items and a campaign save to
verify native transfers, stale selections, owner isolation and saved-bag contents.
Never install either fixture as a live module's load script.

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
