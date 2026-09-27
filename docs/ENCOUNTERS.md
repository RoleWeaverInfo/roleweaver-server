# Persistent encounters and the AI DM

Use **Encounters** to build reusable, shared-world situations that can recover after a
server restart. **Live Encounters** remains a separate workspace for temporary placement.
The AI DM helps draft a scene, guides its existing NPCs, advances approved stages and
selects an approved outcome. Once configured and armed, it needs no online DM or open browser.

## Set up an unattended encounter

1. Create the participating profiles in **NPCs**. Set their personality, permitted lore,
   creature settings and actions. The assistant uses existing profiles; it does not silently
   create new ones. Create one profile per actor, up to eight actors per encounter.
2. Open **Encounters**. Describe the situation in the AI DM panel and click **Prepare proposal**.
   Allow combat in the proposal only if you want it. The result is a draft, not an activation.
3. Click **Review proposal in editor**. Check the cast, public facts, each actor's private
   knowledge, boundaries, stages and outcomes. Give stages clear transition conditions and
   outcomes observable completion conditions. Keep notes that no model should see in
   **DM-only notes**. You can also build everything manually.
4. Enable **Let the AI DM monitor and advance approved stages and outcomes**.
   Leave **Resume armed encounters after game or companion restart** enabled for unattended
   recovery. Optionally replay a completed encounter after the next game restart.
5. Choose a proximity mode. **Greeting only** opens a peaceful conversation.
   **AI combat decision** requires explicit combat permission and conditions; native scripts
   require a warning, grace period, and later player reply before attacking. **Timed warning**
   is available for manual scenes, but timed attacks cannot be combined with AI DM automation.
6. Optionally enable NWN Intimidate, Persuade and Bluff checks and set their DCs and limits.
   These require the proximity trigger. Game scripts roll using the actual player's skill;
   the model cannot choose bonuses or results. Results are reused for the same player, skill,
   actor and activation. See [Social checks](SOCIAL_CHECKS.md).
7. **Save definition**. Edits affect the next activation, not an already running snapshot.
8. Place actors in your module with their normal Role Weaver bindings, or use **Spawn missing
   actors at DM**. With AI DM enabled, that button requests persistent placements. Existing
   actors stay in place: change temporary actors to persistent in **NPCs** yourself. Your world
   must permit persistent spawning to use the latter method. All trigger actors must be in
   the same area, within 30 metres of the first actor.
9. Set actors to **AUTO**. Review the setup messages. Enable NPC startup AUTO if you want
   actors automatically available after restart. A recorded location checks the area; it
   does not teleport actors there.
10. Click **Arm for automatic start / recovery**. This is approval to run the saved snapshot
    once its actors, LLM configuration and bridge are ready. It can wait while the game is
    offline. **Start now** instead requires actors to be ready immediately.

Installing this update requires compiling the updated bridge scripts and restarting NWN
once (encounter protocol **6**). Creating and editing encounter definitions afterwards does
not require rebuilding the module. Module-placed creatures still need the normal binding
scripts; persistent dashboard placements use the existing placement restorer.

## Monitoring and DM control

The AI DM monitor shows the current phase, summary, review count, recent decisions and
recovery/error messages. The DM may send additional direction, pause the AI DM, or resume
it. Manual stage/outcome overrides are available below. Directions cannot expand game
permissions. Ordinary NPC dialogue still uses the configured safeguards.

The director uses recent dialogue, confirmed game events, actor availability/combat state,
nearby player observations and verified social-check results. It cannot invent a payment,
spawn an arbitrary creature, execute scripts, award rewards or control a player's actions.
Actor goals use each actor's existing permissions. Future stage plans and outcome conditions
are for the director; actors receive their current stage and individual guidance. DM synopsis
and DM-only notes are excluded from model prompts.

A scene is shared by everyone in the world, not a separate quest per player. Reserved actors
stop their ordinary patrol/check-in duties. Completion or cancellation releases them.
The optional trigger has one spokesperson (the first actor), a fixed centre at that actor's
position when armed, and one selected player per activation. It checks visibility and hearing;
DMs do not trigger it. The AI DM must choose an approved outcome to finish its activation.
When a trigger is enabled, completion waits for game confirmation; combat may delay it.

**Retreat** requests an approved destination, with game validation. Pursuit limits and
low-health withdrawal can return actors home; neither heals, teleports nor revives them.
Native game AI still owns combat and pathfinding. Pause is not an instantaneous combat freeze;
use direct NPC controls or possession as needed.

## What survives a restart

- Saved definitions, the approved run snapshot, current stage, direction and NPC memories persist.
- An active, approved auto-recovery encounter waits for its actors to reconnect in AUTO, then
  resumes without a DM. A missing, dead, possessed, incompatible or unavailable actor prevents
  recovery; the dashboard explains the blocker. Recovery does not duplicate or revive actors.
- A new game session creates fresh activation authority, observations and dice-check history.
  It retains the saved stage but does not resume a half-finished warning or pending attack.
- A companion-only restart in the same game retains the activation and check ledger. The director
  rechecks current observations before continuing. A lost roll acknowledgement is not rerolled.
- Deliberately paused or cancelled encounters remain so. An AI DM pause also survives recovery.
- Completed encounters remain completed unless replay on the next game restart was selected.
  Replay begins at the first stage; character memories are preserved.
- Manual scenes, and scenes with recovery disabled, pause after restart as before.

The service must itself start on boot (the installed companion systemd service provides this).
Recovery also depends on the world restoring its actors. Saving a definition alone does not arm it.
A provider failure holds new AI combat decisions and retries after 60 seconds; it does not stop
native combat already underway. Reviews share the existing request limiter, run one at a time,
and normally have a 10-second interval. Persistent runs do not stop at the live activation's
60-review limit; unchanged observations do not generate new reviews. Monitor usage for long runs.

Definitions and run state are included in recovery/manual backups. Use this version or newer
when restoring backups with these fields. The monitor keeps the latest 20 director decisions
and 50 encounter events. Unsaved editor changes have a leave-page warning, not draft recovery.

## Suggested tests

- Create a peaceful dispute. Enter the greeting radius and resolve it through conversation.
  Check the director chooses a defined stage/outcome without granting imaginary rewards.
- Test refusal and an unexpected proposal in an explicitly authorized combat scene. Check
  warnings, game dice, later-reply timing, retreat and game-confirmed completion.
- Restart NWN mid-scene with no DM logged in. Verify the saved stage resumes after actors
  return, a stale warning does not become an attack, and NPC memories remain.
- Restart only the companion; verify the same activation and check results remain.
- Pause the scene deliberately, restart, and verify it stays paused. Repeat with AI DM pause.
- Finish a scene with replay disabled, then enabled. Check only the latter restarts at its
  opening stage after the next game restart.
- Disconnect an actor or pause it. Verify recovery waits and the monitor explains why.

## Developer map

`roleweaver/encounters.py` owns definition validation and saved lifecycle.
`persistent_director.py` adapts saved runs to the shared director, handles proposals and recovery.
`director.py` validates bounded model decisions; `live_director.py` schedules and applies them
through scope-specific persistence and command authority. `social_service.py` dispatches native
rolls. `bridge/rw_encounter.nss` and `rw_social.nss` validate persistent versus live ownership,
activation, actor epoch and native actions. `static/encounters.js` owns this dashboard page.

Tests: `tests/test_persistent_director.py`, existing encounter/live/director suites, and
`tests/persistent_director_native.nss` in a disposable native world. Never run native fixtures
inside a production module.
