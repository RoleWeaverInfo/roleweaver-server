# Live Encounters

Use **Live Encounters** for temporary DM-directed scenes during a running game.
Use **Persistent Encounters** for the existing saved encounter library and recurring
world scenes. These sections have separate records and controls. Existing saved
encounters are not moved or converted by this update.

Install the updated bridge once, then restart the module to load it. After that,
creating, placing, starting, pausing and cleaning up live scenes requires no restart.

Live encounters remain until explicit cleanup or a module/server reset, including
when the DM logs out and returns as a player. Start NWN with `-reloadwhenempty 0`
to prevent it from resetting the module when the last person disconnects. The demo
and new-server launchers include this setting by default. Existing-server owners
should add it to their own launch command if they want scenes to survive an empty
server. Applying a changed launch flag requires restarting NWN once.
The page reports whether the new live bridge is connected.

## Place a scene

1. Log in as DM and release possession. Open **Live Encounters**.
2. Name the scene, select a saved NPC profile and choose 1–8 creatures. Each creature
   gets a new profile copied from that source; existing NPCs and their memories are
   not reused or moved. This first version uses one source profile per group.
3. Choose the creature source. **Profile settings** builds the appearance, class
   and level saved in NPCs. **Installed blueprint** uses a creature resref already
   available to the running server. It retains the blueprint's statistics, equipment
   and scripts; availability is checked during placement, not by the preview.
   A monster appearance alone does not grant monster abilities.
4. Fill in the shared facts, purpose and behavioral limits.
5. Stand at the desired spawn point and click **Mark spawn at DM**. Move to the
   desired trigger centre and click **Mark trigger at DM**, or use the spawn point
   for both. Marks last 15 minutes and belong to this module session. Both points
   must be in the same area and within 20 metres of each other.
6. Choose **Conversation only** or **Proximity warning**. For proximity, configure
   the warning, radius, leave distance, grace period and optional attack. Choose
   one activation or automatic repetition. A repeating trigger waits for the cast
   to return home, recover above its retreat threshold and leave combat, plus
   10 seconds with no players inside the trigger radius.
7. Click **Preview scene**. Review the frozen settings and relative-position diagram.
   This does not create objects. The diagram does not show terrain or guarantee
   walkability. Editing the form invalidates its preview; previews expire in two minutes.
8. Click **Place temporary creatures**. Wait for every placement to be confirmed.
   Creatures are staged with AI paused; the proximity trigger is not armed yet.
9. Click **Start / resume**. All actors must be alive, unpossessed and out of combat.
   Dialogue starts and, if configured, the game confirms **Trigger armed**.

The trigger is currently a circular region checked by the existing game scripts,
not an Aurora trigger object. It starts the warning, rather than spawning a hidden
cast. Players still need visibility/hearing to the spokesperson; walls can prevent
activation. The original spawn and trigger points stay fixed during an activation.

Native creature blueprints can have hostile AI or custom scripts which act
independently of Role Weaver. Test those blueprints before using a peaceful or
timed-warning scene. The model cannot override combat permissions, award items or
gold, or create arbitrary scripts.

## Pause and clean up

- **Pause** stops renewing the trigger and pauses AI dialogue. The game rejects
  stale commands. This is not an instantaneous native-combat freeze.
- **Start / resume** begins a fresh activation after checking the cast. It is an
  explicit DM action, so it can start another activation even for a one-time scene.
- **Clean up creatures and trigger** disables the scene and removes only creatures
  with that scene's ownership token. It does not remove existing world NPCs, unrelated
  creatures, profiles or memories. Release possession before cleanup.
- Cleanup is complete only after all game acknowledgements arrive. Rejected or
  missing confirmations stay visible; retry cleanup after resolving the problem.
  Partial placement is not automatically rolled back. Clean it up and preview again.
- A companion restart pauses live scenes and retains their ownership journal for
  recovery. A module restart expires them: they do not automatically respawn.
  Clean up live scenes before restoring a Role Weaver backup.

There can be up to 10 unresolved live scenes, subject to the bridge's existing
32-bound-NPC limit. Recent ended scenes remain in the list (up to 40). Profiles and
memories remain in NPCs after cleanup and may be deleted there when no longer needed.

## Suggested playtest

1. Preview a one-creature conversation scene; verify nothing appears yet.
2. Place it beside the DM. Confirm the source NPC remains untouched and the copy
   is paused. Start, reconnect as a player, and speak to the copy.
3. From the dashboard, clean up; confirm only that copy disappears.
4. Place a three-creature proximity scene with radius 5, leave distance 10, grace
   15, pursuit limit 20 and retreat health 25. Start while outside its radius.
5. As a player, approach and withdraw before the deadline: no attack should occur.
6. Repeat using the repeat option. Remain through the deadline, retreat beyond
   the pursuit limit, wait for return and the quiet cooldown, then approach again.
7. Try an unavailable blueprint. Verify a rejected placement is shown, no existing
   creatures are touched, and cleanup safely closes the partial scene.

## Developer notes

`roleweaver/live_encounters.py` owns the separate live-scene API and journal.
`roleweaver/static/live-encounters.js` is the dashboard editor and preview.
`bridge/rw_live.nss` validates session/world/DM and creature ownership for placement
and cleanup. `rw_encounter.nss` supplies the shared warning/combat runtime, with a
captured anchor and explicit repeat flag for live scenes.

The service saves ownership before dispatching non-atomic spawn requests. Previews
are single-use; cleanup installs a native tombstone so a queued spawn cannot recreate
a cleaned scene. Missing acknowledgements are never treated as successful removal.
The journal is local operational state, not a persistent-world encounter definition
or a backup respawn recipe. The AI DM assistant prepares proposals for these same validated APIs; the DM reviews and places them.


## AI DM Assistant: describe, review, place

The assistant is inside **Live Encounters**, not a separate page. Configure an
LLM provider first. Describe the scene and press **Prepare proposal**. It fills the
editable setup with a supported proposal; it never spawns or starts anything.
Review the proposed profile, purpose, limitations and combat setting. Mark locations
with the connected DM, preview, then place and start using the existing controls.
The manual setup remains available without an LLM.

Proposals create 1–8 copies of one existing NPC profile. They do not create new
profiles, mixed casts, quest mechanics or automatic rewards. Payment requests and
NPC-to-NPC combat require the relevant actor permissions after placement; a
proposal does not grant them. Unsupported requests appear in the proposal's limitations. Timed attacks can only be
proposed when the DM checks the combat-proposal permission; existing preview/start
confirmation still applies. Narrative text alone cannot create game mechanics.

Under **Manage live scenes**, expand **Ask the assistant about this scene** for an
on-demand assessment or direction. It sees the scene snapshot and game log and may
suggest start, pause or cleanup. The DM clicks the suggested operation; the ordinary
state validation and cleanup/combat confirmations still apply. This on-demand assessment is separate from the optional autonomous director below.
Neither reads all player chats nor directs unrelated scenes. World events remain
authoritative and the assistant may be wrong about a situation.

Requests use the configured provider and appear in Usage as `live_assistant`.
One assistant request runs at a time, without holding the game-processing lock.
Draft proposals are editable browser state, not durable scene records until placed.

## Conversation-driven combat

Choose **Conversation-driven combat** under Activation, enable attack permission,
and write **DM conditions for conversation combat**. This is separate from proximity
attacks: the timer never starts combat by itself. The first actor is the spokesperson
and decides for the whole cast. Conditions are interpreted by the LLM; game scripts
check permission, scene ownership, target, warning, distance and timing, not the
semantic truth of the model's reasoning.

The spokesperson automatically speaks the configured **Opening line** once when
an eligible visible player enters the trigger radius. The player can answer naturally;
their conversation selection is set to this NPC. An existing conversation with another
NPC is not interrupted. The opening is separate from the combat warning and does not
start a combat timer. The encounter holds that player as its participant until they
leave or the activation ends. Legacy scenes use a neutral default opening.

The spokesperson can negotiate, issue the exact DM warning, request an attack on a
later player reply, or end the activation peacefully. Combat requires the same player,
a delivered warning, the grace period having elapsed, a new player reply, visibility,
an active scene, valid actors and a current command. DM characters and bystanders
cannot be selected by the model. Leaving the configured leave radius cancels the
warning. Silence never causes an attack; a warning expires two minutes after the
grace period. Existing pursuit and low-health retreat rules still apply. Successful
negotiation should select a peaceful resolution. Enabled payment offers use the
game-confirmed exchange system; a spoken claim of payment is not a receipt.
See [payments and NPC combat](PAYMENTS_AND_NPC_COMBAT.md).

Installing this capability requires one game-script update and restart. Later live
scenes need no restart. Existing scenes keep their saved behavior; create a new one
to use conversation combat. If the bridge is outdated, starting this mode is rejected.

### Robber example for Describe your encounter

Enable **Allow the proposal to include combat**, then paste:

> Create one roadside robber using the existing road_robber profile. He demands
> five gold but prefers a peaceful solution and fears injury. Keep replies short.
> Opening line: "Hold there, traveler. Five gold to pass, unless you have a better offer."
> Use conversation-driven combat, not a timed attack. Negotiate first. Warn if the
> player clearly refuses and remains confrontational; attack only if they clearly
> refuse again after the warning and grace period. Accept a credible offer of help
> or back down if convincingly intimidated. Questions alone are not refusal. Never
> claim payment or an item exchange occurred without game confirmation. Exact warning:
> "Last chance. Back away or settle this peacefully, or I will fight you."
> Set grace to 10 seconds, leave distance to 10 metres, pursuit to 20 metres and
> retreat health to 25 percent. Run once, without automatic repetition.

Review the proposal and conditions, mark locations, preview, place and start. Test
refusal, peaceful negotiation, walking away, silence, and another player's attempt
to interrupt. The game-confirmation log reports warning, attack, peaceful resolution,
and rejected requests. Safeguard failures or malformed LLM output issue no decision.

## Autonomous AI DM

Optional Intimidate, Persuade and Bluff checks can now resolve uncertain player
influence using server-confirmed dice before an NPC replies. Configure them under
**Manage live scenes → Optional NWN social checks**. See [Social checks](SOCIAL_CHECKS.md)
for setup, limits and playtests. They are disabled by default and work with or without
the autonomous director.

Live and persistent encounters use the same reasoning module through separate
adapters. The controls below concern live scenes; see [Persistent encounters](ENCOUNTERS.md)
for saved definitions and restart recovery. A live scene still expires on game restart.

1. Describe, preview and place the scene as usual. For combat, choose conversation
   combat with explicit conditions; independent timed attacks cannot be directed.
2. In **Manage live scenes → Autonomous AI DM**, click **Enable autonomous direction**.
3. Start the scene. The DM may log out. No ongoing DM connection is required.
4. Read **Current situation** and **Recent decisions**, or use **Give direction**.
   **Pause director** preserves NPC dialogue but holds new conversation-combat
   decisions. It does not cancel combat already underway. Resume when ready.

The director reviews up to 30 recent messages from this scene's actors, confirmed
encounter events, actor action status, and nearby player presence. Dialogue is
untrusted testimony, not proof of payment or a completed action. Raw account/player
identity keys are replaced with scene-specific visitor aliases, and configured PII
scrubbing applies. It does not read unrelated NPC conversations. Summary text is
for the DM; only an actor's individual immediate goal enters its dialogue context.

It can guide negotiations and individual goals, hold escalation, and request peaceful
resolution. NPCs choose their existing allowed actions during dialogue; the director
does not yet dispatch arbitrary movement, spawn reinforcements, grant rewards, or
create scripts. Resolution is confirmed by the game before being marked finished.
A finished activation does not automatically repeat. Fresh Start after Pause creates
a new activation with a fresh review budget. Walking away, connection loss and death
are observations, not automatic proof of success. All actors confirmed dead ends the
director locally. Nearby presence is limited to the encounter area/radius and sight;
an absent player may have left or disconnected, and the director must not guess which.

Routine reviews occur only when the snapshot changes, at least ten seconds apart, one in
flight globally, and share request-rate limits with dialogue. Each activation permits
60 attempts, including failed or stale reviews. Usage is recorded as `live_director`.
Provider failures clear guidance, hold new combat decisions and retry after 60 seconds.
The director receives the game's attack-readiness flag from the latest player reply:
this confirms the warning, elapsed grace period and subsequent reply for that participant.
It does not infer elapsed time from dialogue or demand an additional clock confirmation.
Normal waiting uses `continue`; an intentional `hold` still blocks escalation. Readiness
does not itself authorize combat: DM conditions, current native checks and the NPC's
action choice still apply. Old activations, sessions, epochs and expired observations
cannot supply readiness for a new scene.
An eligible post-warning player reply now requests a priority review before its NPC
response, bypassing the routine ten-second cooldown. If another review occupies the
single director slot, it is queued for priority processing. Request budgets, the
60-review activation limit, DM pause and provider-error backoff still apply. The NPC
then receives the updated direction and current action choices; an already delivered
warning is not offered again once the game confirms attack readiness. Provider response
time still affects latency. Grace time remains configurable per encounter.
New dialogue, a changed DM direction, pause, cleanup, or a new activation invalidates
an outstanding review. A paused director does not keep spending tokens.

The director state and decision log are saved with the live scene. Companion restart
still pauses live scenes for review; a game/module restart expires them. This is not
persistent encounter recovery. Installing the director bridge requires a one-time
server restart; creating subsequent live encounters does not.

### Unattended robber playtest

Enable the director on a fresh robber scene, start it, log out as DM, then return as
player. Approach for the opening. Try a credible peaceful offer, clear repeated
refusal after warning, and walking away. Verify that a peaceful resolution disables
further escalation. Check the summary distinguishes a claimed payment from a real
transfer. Try a second player arriving, disconnect during negotiation, and pause the
director while a model request is pending. No response or unavailable provider must
not cause an attack. Combat already begun follows native pursuit/retreat rules.

### Proposal response formatting

Proposal preparation allows more output space and retries once if the model returns
malformed or truncated JSON, within the original request timeout. The retry can use
up to 8,192 output tokens and is included in usage tracking. A complete JSON code
fence is accepted; incomplete JSON is never repaired into a proposal. If retry fails,
the instructions remain in the editor and a readable error is shown. No placement
occurs. Autonomous director reviews retain their existing backoff rather than this
extra proposal retry.
