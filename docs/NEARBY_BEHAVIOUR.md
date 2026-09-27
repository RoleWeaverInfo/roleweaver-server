# Nearby movement and interactions

In **Controlled Actions**, select an NPC and enable approved actions. Under
**Nearby behaviour**, choose its permissions and save. All new permissions are
off for existing and new profiles until the DM enables them.

* **Approach:** walk near a currently visible object or non-player character.
* **Doors:** approach and open or close usable, unlocked, non-transition doors.
  Normal module door scripts still execute. Test custom doors before enabling.
* **Talk:** approach another bound AI NPC and begin one question and one reply.
  The recipient must enable **Accept these nearby check-ins**, be idle in AUTO,
  and not be speaking to a player. There is a five-minute per-pair cooldown.
* **Seating:** add genuine chair placeable tags, one per line. Visible placeable
  tags are displayed beneath the field. Tags may match multiple chairs, so use
  unique tags in Aurora for individual approval. Containers cannot be seats.

Receiving nearby check-ins does not require enabling the recipient's own movement.
Existing patrol check-ins remain governed by their separate route configuration.
No player identities, inventories, locks, traps, scripts or quest variables are
added to model perception. Target references are opaque; tags stay in DM metadata.

## Try it

1. Enable Approach for a nearby NPC, save, and resume AUTO.
2. Say “Please walk over to that table.” Alternatively use **Test saved action**.
3. Enable Doors and ask it to open a visible door. A locked door must remain locked.
4. Approve a chair's tag and ask the NPC to sit there. An occupied chair is rejected.
5. Enable Talk on the speaker and Accept on the recipient. Ask the speaker to go
   check on that NPC. Its current player conversation focus is released when the
   visit starts; address it again to interrupt. The two NPCs speak after arrival.
6. Repeat while pausing or possessing the moving NPC: its action must stop.

Dynamic choices also let the model choose a relevant action during an ordinary
reply. This version does not add an idle LLM planning/wandering loop or arbitrary
object-use. Visits are general check-ins, not multi-step delivery of player tasks.
Check-ins use two LLM requests plus configured safeguard reviews. Movement and
object interaction use the existing dialogue request and no additional planning
request.

## Limits and outcomes

Targets must be visible within the chosen 2–12 metre radius, in the same area.
Movement uses normal NWN pathfinding and times out after 30 seconds. The bridge
checks the actor and target against the starting position on each tick, with a
one-metre tolerance for the actor. This is a movement bound, not a physical fence
or a guarantee that every path is navigable. Moving or disappearing targets can
interrupt actions. Existing module AI/heartbeat scripts can interfere.

Combat, death, pause and DM possession interrupt actions. Door and seating effects
are checked by the game, rather than treating dispatch as success. The dashboard
shows the result and subsequent dialogue receives the last action status. The NPC
is instructed to describe intent until the game confirms success. A completed sit
retains the sitting action; Stop, another action, or module AI can make it stand.

Permissions are included in existing recovery backups. Runtime targets and jobs
are not durable and are never replayed after restart. Encounter actors do not get
these dynamic choices while reserved for an encounter. NPC conversation hooks do
not recursively launch more conversations.

## Developer notes

`nearby.py` validates policy and builds permitted choices from fresh perception.
`rw_core.nss` maintains a bounded, observer-specific target map. `rw_nearby.nss`
validates references and monitors native movement and interaction outcomes;
`rw_actions.nss` provides the normal epoch/session/expiry/control gates. Model
output supplies only one precomputed action ID; it cannot supply coordinates,
engine IDs, chair tags or executable scripts. The companion supplies validated
permission parameters over the existing trusted local bridge.

Install the updated companion and recompile/install the bridge together. The
new include `rw_nearby.nss` is included by the add-on preparation/build tools.
An older bridge receives no new choices until it advertises `nearby_protocol=1`.

Requests to talk to another NPC select a live visit, not a saved landmark associated with that NPC. Recognisable social requests exclude saved-location movement and approach-only actions; unavailable visits must not fall back to a table or patrol stop.
