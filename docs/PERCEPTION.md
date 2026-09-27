# NPC perception

NPCs receive a bounded view of their surroundings when preparing a player reply or
an NPC-to-NPC check-in. In **NPCs**, select a character and expand **What this NPC can
see** to inspect the same filtered snapshot used by the model.

The detailed bridge reports:

- Area name, the NPC's own rough injury condition, and whether it is fighting.
- Visible characters: approximate distance, direction relative to the observing
  NPC's facing, rough injuries, fighting/not fighting, and game faction attitude.
- Doors: open/closed and usable status.
- Containers: open/closed and usable status, without any contents.
- Other visible placeables: name, distance, direction and usable status.
- Role Weaver-enabled merchants, without revealing their stock or prices.

The current bridge scans the current area without a 12-metre distance cutoff.
Walls and other geometry block observations through the game's line-of-sight test.
Ordinary visible creatures are not restricted to the engine's local perception
radius; stealth and invisibility effects still require engine detection. DMs and
DM-possessed creatures are excluded. Scans refresh every two bridge ticks.

For crowded worlds, each scan examines up to 1,024 area objects and reports up to
256 visible objects. The inspector flags incomplete scans. This is not a guarantee
that omitted objects are absent. Directions describe facing at observation time.
More objects increase normal dialogue context/token usage; scans do not make
additional LLM requests. Movement permissions and hearing ranges are unchanged.
Older bridge protocol 2 retains its 12-metre/24-candidate behavior.

Player names remain **Unidentified traveler**. Names learned through the existing
conversation/memory system are not automatically attached to nearby anonymous
figures. Tags, object IDs, inventories, locks, traps, quest locals and private lore
are not exposed by this feature. A hostile game relationship is not evidence of
intent or guilt. Object names are untrusted text, not instructions to the model.

Stale scans are withheld from new prompts. The inspector says when no current
observation is available. The basic old bridge remains compatible until the new
compiled scripts are installed, but supplies fewer details.

This update gives information, not additional action permissions. It does not
automatically make NPCs open doors, loot containers, start fights, or react to every
passing character. Existing DM-approved actions still determine what they may do.
Scans themselves are not saved as long-term memories or sent as extra LLM requests.
They add context to normal conversations and check-ins.

## Playtest

1. Select an AUTO NPC and open its perception inspector. As a player, approach and
   ask what the NPC sees nearby. It should describe relevant visible surroundings.
2. Ask your name without introducing yourself. Proximity must not reveal your
   character's displayed name.
3. Open and close a nearby visible door; wait two seconds and ask about it again.
4. Ask what is inside a closed chest, whether it is trapped, or where a door leads.
   The scan supplies none of those facts. The NPC may know independently authored
   lore, but must not invent an inspection or claim access to hidden contents.
5. Stand more than 12 metres away in the same open area: you should still appear.
   Move behind a wall and check that you disappear from the next scan. Also test
   stealth and invisibility: undetected characters must not appear.
6. Compare friendly, neutral and fighting creatures. Verify the model does not
   turn a faction relationship into invented motives or an unauthorized attack.

## Code map

- `bridge/rw_core.nss`: bounded game scan and cached observation timestamp.
- `roleweaver/perception.py`: field allowlist, player anonymization and freshness.
- `roleweaver/services/dialogue.py` and `roleweaver/checkins.py`: snapshot delivery.
- `roleweaver/provider.py`: interpretation and disclosure instructions.
- `roleweaver/static/perception.js`: read-only selected-NPC inspector.

The perception payload uses `perception_protocol=2`; the existing patrol
`awareness_protocol=1` remains unchanged. No additional NWNX plugin is required.
