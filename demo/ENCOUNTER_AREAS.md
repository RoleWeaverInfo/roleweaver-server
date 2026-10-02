# Forest and cave demo areas

The development demo keeps Crown Hall as its starting area and adds two side doors
near the middle of the hall. Directions below assume you face the throne from the
main entrance.

| Door | Destination | Intended demonstration |
| --- | --- | --- |
| Left / west: **Forest Path** | **Crownwood Forest Path** (`rw_forest`) | A robbery on a woodland trail |
| Right / east: **Troll Cave** | **Hollowstone Cave** (`rw_cave`) | Grust and Morga holding Elana Voss hostage |

Both areas have a return exit to Crown Hall, with an arrival point away from the
door. The forest has a short path, trees and space to retreat. The cave has an open
compact chamber with room to approach the trolls and move around the hostage.
Each uses
standard NWN tiles, lighting, ambient sound and music; no custom HAK is required.

Fresh demos also import two armed **Persistent Encounters** from `demo/content.json`.
Rusk waits on the forest path; Morga, Grust and their captive Elana Voss wait in the
cave. The AI-DM Assistant opens each scene when a player approaches within six
metres of its lead actor. An online LLM provider is needed for its decisions.
The waypoints below are editing markers; the encounter settings supply the triggers.

Rusk demands 30 gold (minimum negotiated payment: 10). Morga demands 100 gold for
Elana (minimum: 75). Requests use the real exchange/payment system: saying that
you paid does not count as a receipt. Persuade, Bluff and Intimidate checks use DC
15 and the game's character statistics. Both scenes support bargaining, withdrawal
and bounded combat following an explicit warning and continued defiance.

Elana's **May join the encounter attack against the player** setting is off. Grust
may threaten her, but his separate permission to attack her requires warned,
player-initiated combat while the hostage situation remains unresolved. Refusing
payment, failing a social check or merely displaying a weapon does not authorize it.
These are configured limits, not a guarantee of any particular LLM response.

The scenes resume after a server restart without a DM online. Completed scenes
are configured to repeat on the next restart when their actors are available;
dead actors are not automatically resurrected. In the dashboard, use Persistent
Encounters to pause, edit or rearm a scene. Live Encounters remain separate.

## Open and edit the map

1. Back up `demo/world/YourWorld_Fixed.mod`.
2. Open that module in the Aurora Toolset. Its area list contains the throne room,
   Crownwood Forest Path and Hollowstone Cave.
3. Move scenery and staging waypoints as desired. Keep the two hall doorways and
   their arrival points clear. Preserve the area tags, door links and module event
   scripts unless you intend to update the integration too.
4. Save the module. Stop and rebuild your demo as described in
   [CUSTOMIZE.md](CUSTOMIZE.md#edit-or-replace-the-world), then start it again.

Existing installed demos retain their current module until they are rebuilt from
the updated source. Rebuild from the new package's source to use its current bridge and map.

## Encounter staging points

Coordinates are metres in the area. NPC profiles, placements and encounter settings
remain separately editable in the dashboard.

| Area | Waypoint tag | Purpose | X, Y |
| --- | --- | --- | --- |
| Forest | `rw_arr_forest` | Arrival / return exit map note | 25, 18 |
| Forest | `rw_rob_trigger` | Suggested approach trigger centre | 25, 27 |
| Forest | `rw_rob_stage` | Lead robber's confrontation point | 25, 35 |
| Forest | `rw_rob_left` | Left lookout | 20, 37 |
| Forest | `rw_rob_right` | Right lookout | 30, 37 |
| Forest | `rw_rob_retreat` | Robber retreat destination | 25, 46 |
| Cave | `rw_arr_cave` | Arrival / return exit map note | 25, 18 |
| Cave | `rw_troll_trigger` | Suggested approach trigger centre | 25, 24 |
| Cave | `rw_troll_grust` | Grust | 18, 28 |
| Cave | `rw_troll_morga` | Morga | 26, 29 |
| Cave | `rw_troll_hostage` | Elana Voss | 22, 36 |
| Cave | `rw_troll_escape` | Escape point near the entrance | 25, 20 |

When you move these points in Aurora, update any saved encounter placements and
destinations separately. Stable waypoint names alone do not move saved dashboard
coordinates.

## Quick in-game check

1. Enter Crown Hall and use the left door. Walk along the forest path, then return
   through its southern exit.
2. Use the right door. Walk to the back of the cave and return through its entrance.
3. Check the hall's original NPCs, furniture and investigation still behave as before.
4. Approach Rusk on the forest path and Morga in the cave. Each should initiate
   its demand. Try bargaining, a genuine payment, or withdrawing beyond ten metres.
5. On a separate run, test a failed negotiation followed by explicit defiance after
   the warning. Check the encounter log for rolls, payments and combat decisions.
   Elana must not be ordered to attack the rescuing player.

## Developer checks

`tools/expand_demo_world.py` records the original area construction. It works on a
copy of the earlier, one-area demo and refuses to overwrite existing areas or an
existing output file. **Do not rerun it on the expanded module**; edit that module
in Aurora instead.

Run the structural/preservation checks from the repository root:

```bash
python -m unittest tests.test_demo_expansion -v
```

For a native geometry check on Linux, with NWN and `nwnsc` already installed:

```bash
python tests/run_demo_areas_native.py \
  --runtime "$HOME/nwserver" \
  --compiler "$HOME/bin/nwnsc" \
  --module demo/world/YourWorld_Fixed.mod
```

This starts a private, temporary test instance on UDP 5198, walks creatures through
the new areas and transitions, then stops only that instance. It does not load
NWNX or access the live Role Weaver database. Its temporary log directory is printed
at the end. Actual client rendering and mouse interaction still need the in-game
check above.
