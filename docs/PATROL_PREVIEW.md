# Patrol duties and NPC check-ins

Patrol duties use saved destinations and game-confirmed movement. Optional short
NPC check-ins let guards speak to other characters along the route. Broader
[perception](PERCEPTION.md), [nearby behavior](NEARBY_BEHAVIOUR.md) and
[inventory actions](INVENTORY_TASKS.md) are documented separately.

## Optional NPC check-ins

In Patrol duty, add one line for each stop that should trigger a conversation:

```text
patrol_merchant=merchant_one
patrol_wizard=rq_wizard
patrol_cleric=rq_cleric
patrol_holt=rq_holt
```

Use your own saved stop IDs and target NPC profile IDs. Each stop must be on the
route. Both NPCs must be idle in AUTO, visible to each other and within six metres.
An unavailable target is skipped; the guard does not chase it. Keep check-ins blank
to disable them. Save the patrol after editing. Default pair cooldown is five
minutes (configurable from 60 to 3600 seconds); attempts also consume cooldown.

The guard asks one short question and the target replies once. Both turns pass
through input/output safeguards and each requires game acknowledgement. Confirmed
speech is kept in each NPC's conversation history under an `npc:` identity. Received
lines are attributed unverified reports, not authoritative lore. The latest six
reports may inform later dialogue; older pair history remains bounded by normal
conversation retention. Private player transcripts are not sent to the other NPC.

Check-ins share the global request budget, allow only one background generation
at a time, and have a 90-second overall timeout. They consume up to two generation
requests plus enabled review requests; Usage records generation as `npc_checkin`.
Player conversation, possession, combat, distance, or Stop cancels the exchange.
Patrol continues after its normal wait. Cooldowns survive companion restarts.

Test one stop first: hear a question and reply, confirm patrol resumes, then repeat
while speaking to either NPC or possessing it. Try a paused or distant target and
a blocked/failed provider response: there should be no repeated or delayed speech.

## Configure a guard

1. Install the updated companion and recompile/import the bridge scripts using
   the existing module integration procedure. Restart the game server to load
   them. Older scripts can still handle conversations but cannot start patrols.
2. In **Controlled Actions**, record at least two locations from your DM's
   position. Use the same uniquely identified area and keep successive stops
   within the existing 40 metre movement limit. Check the closing leg too.
3. Select your guard and save its allowed walk destinations and enabled actions.
4. In **Patrol duty**, enter a purpose, the location IDs in route order separated
   by commas, and the time at each stop. Enable and save the patrol.
5. Set the NPC to AUTO. It begins after an initial five-second settling period.

Purpose is context for the NPC's replies, not permission to execute additional
actions. Patrol movement itself makes no LLM requests. Settings are included in
the existing controlled-actions backup data. In-flight tasks are not persisted.

## Playtest

- Confirm the guard visits each stop and waits before continuing.
- Select Speak or address it during movement: it should stop, answer, and resume
  its unfinished leg after the conversation expires and the dwell delay passes.
- Pause or possess the guard: movement must stop. Release possession and explicitly
  resume AUTO as usual.
- Press **Stop NPC action**: background patrol stays stopped until you save/restart
  its patrol settings. This does not pause ordinary conversation.
- Block a route: a timeout stops the patrol instead of repeatedly retrying.
- Restart the companion or module: the route starts from its first stop; old
  commands are not replayed.
- Ask about nearby objects: observations cover up to 24 nearest candidates within
  12 metres, filtered by line of sight and creature perception. Player names,
  inventories, chest contents and secrets are not supplied. Seeing an object
  grants no permission to manipulate it.

## Developer notes

`roleweaver/patrol.py` owns validation and the duty state machine. Policies are
nested in each NPC's controlled-actions entry. Only a fresh state event advertising
`awareness_protocol=1` can drive a duty. `rw_actions.nss` independently checks
conversation engagement before starting and during patrol movement. Existing
session/epoch checks, movement limits and cooldowns remain in force.

`rw_core.nss` supplies the bounded visual snapshot; `provider.py` labels object
names as untrusted descriptive data. Store contents still come exclusively from
the existing merchant snapshot. Perception is currently evaluated on each state
report; measure game CPU with larger NPC populations before widening this scope.

Next increments: structured NPC check-ins with turn limits, richer diagnostics,
and DM-authored encounters using the same locations and validated action path.
