# Patrol and awareness development preview

This first increment adds deterministic patrol duties and limited visual context.
It does not yet add NPC-to-NPC conversations, autonomous encounters, doors or item
interactions. The published alpha remains unchanged.

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
