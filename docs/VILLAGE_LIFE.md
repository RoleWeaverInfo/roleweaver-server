# Village Life

Village Life is an optional idle routine, disabled by default. It does not manage
an economy, inventory, combat, or occupation schedules.

1. In Controlled Actions, select an NPC and enable controlled actions.
2. Choose a saved **Home location**. Use the existing DM location capture controls
   to record one if needed. The home stays fixed across server restarts.
3. Enable **Village Life**, choose a 2–12 metre radius, and select an activity level.
4. Save permissions and leave the NPC in AUTO.

Quiet selects an activity every 120–240 seconds; Normal every 60–120; Lively every
30–60. Startup has a random 15–45 second delay. Idle breaks are intentional.
The NPC may walk locally, stand quietly, use an approved chair, wave to a nearby
player, visit a willing NPC, or return home after several activities. Wandering
uses normal game pathfinding, never teleportation. Failed activities back off.

Greetings are nonverbal waves, not LLM requests. Each NPC waits at least five
minutes between attempts, and each player has a two-minute village-wide greeting
cooldown. Visits require the existing Nearby talk/receive permissions and use the
existing bounded two-turn AI check-ins. Those conversations can incur LLM usage;
movement, resting and waves do not. Disable visits for a routine with no LLM calls.
Chairs require the existing approved chair tags; otherwise resting means standing.

Player conversations, DM possession, pause mode, combat, patrol duties and
encounters take priority. Actions check the home-area boundary in game, including
visits and seating. NPCs do not transition areas or follow players. If moved out
of their village boundary, they wait for DM intervention or an explicit return-home
instruction. The routine does not move them back across arbitrary terrain.

**Stop current action** halts the routine too. Save permissions again to resume.
Runtime timers and pending jobs are not replayed after restart. Live status appears
under Village Life in Controlled Actions. New scripts require a server restart.

The first activity is a walk. Completed walks alternate with a rest, greeting,
seat or visit; the next activity after a rest is another walk. Failed movement
backs off before retrying. Home locations must be near the NPC when enabling.

Testing pace uses 5-second activity intervals and a 20-second visit cooldown,
favouring available visits between walks. An idle recipient waits for an
approaching NPC visitor rather than wandering away. Conversations remain limited
to two turns and subject to the existing request budget and player interruptions.
Testing increases LLM usage; use the slower paces for normal play.

Village social visits may discuss interests, opinions and information from permitted
lore and memories, rather than only greetings or reports. They remain two turns.
Five-second Testing pauses start after an action completes; movement and LLM
response time are additional. Failed actions retain a longer retry backoff.
