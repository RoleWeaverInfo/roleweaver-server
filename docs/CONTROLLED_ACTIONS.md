# Controlled game actions — 0.24.0

Role Weaver can let an NPC automatically choose a DM-approved gesture, walk or lead a player to a DM-recorded destination, return home, or open a dedicated shop or request a game-rolled haggle during a conversation. Actions are disabled for every NPC until you enable them. Players cannot grant permissions through dialogue.

## Set up a first test

1. Open **Controlled Actions** in the dashboard’s left sidebar.
2. Select an NPC. Enable automatic approved actions, check **bow** or **greet**, then **Save permissions**.
3. Ensure the NPC is in **AUTO** mode. Choose the gesture under **Test and stop**, then click **Test saved action**. Watch the status change from pending to running to completed.
4. To add movement, log into NWN as a DM. Release possession and stand at the destination, in the NPC’s area and within 40 metres of it.
5. Under **Record a destination**, select the DM and enter an ID such as `inn_doorway` and a name such as `Inn doorway`. Click **Record DM position** and wait for confirmation.
6. Select the NPC, check the new destination and **Save permissions**. Test the saved walking action.
7. Reconnect as a player, select or address the NPC, and ask “Could you show me the inn doorway?” The model may choose the approved walk when appropriate. It is not forced to perform every request.
8. During a walk, try **Stop NPC action**, Pause, or DM possession. The controlled action should stop. Resume AUTO when ready to continue.

A 20-second movement/gesture cooldown applies per NPC. Opening a shop is exempt. Gestures depend on the creature model’s available animations. A completed gesture means the game processed its timed animation action, not a visual guarantee for every model.

## Scope and limits

- Actions never move the player. Walking uses ordinary NPC pathfinding to an approved endpoint in the same area, with a 40-metre maximum starting distance and 30-second timeout. This does not define a fenced route; test paths in your module.
- Actions cannot initiate attacks, cast spells, transfer items outside native shop purchases, unlock doors, change quests or execute arbitrary scripts. These would need separate future integrations.
- The NPC must be connected, alive, not possessed, out of combat and in AUTO. Combat, death or control changes interrupt an active action.
- Enabling actions allows Role Weaver to replace the NPC’s current action queue. Custom module heartbeat or AI scripts can conflict with movement. Start with a dedicated test NPC.
- The model chooses only an exact action ID from the NPC’s saved list. It cannot supply coordinates, object IDs, script names or animation constants. An unapproved or malformed choice is rejected.
- Dialogue safety checks run before dispatch. Automatic actions are sent only after the game confirms the accompanying speech was delivered; permissions and NPC state are checked again. Speech expresses intention because an action can still fail.
- The bridge checks the world, game session, NPC control epoch, expiry, action type, distance, state and cooldown. Stop invalidates queued older commands. DM possession takes priority; Role Weaver does not clear the DM’s new action queue.
- The status shown is the most recent action per NPC for the dashboard session. Connection loss or missing confirmation is shown as unknown/timeout, not success.

## Persistence and backups

Named locations and permissions survive app and module restarts and are included in backup format 10. Backups 1–9 remain supported. Backups predating controlled actions clear action permissions and locations; existing legacy action policies gain the new capabilities disabled. Running actions are not stored or replayed. Reconnecting the app to a game already running an action shows its reported status. Persistent NPC placement continues to follow the existing placement rules.

New and duplicated NPC profiles start with no action permissions. Remove a destination from all NPC permission lists before deleting it. Existing destinations cannot be silently repositioned: record a new location and update the selected NPCs. Area identity must be unique when capturing a location.

Action selection shares the existing dialogue LLM request; it adds no separate provider call. The extra instructions and structured reply do use tokens, visible in Usage & Performance. Actual game movement is not part of the provider response time.

See MERCHANTS_AND_LEADING.md for leading, home and merchant setup. Native store stock requires a separate backup of the NWN userdata/database directory.

Per-merchant haggling and stock controls are in the Merchants sidebar tab. See MERCHANT_ADMIN.md.
