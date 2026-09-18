## Review the generated files

Nothing is installed automatically. scripts/ holds NWScript source; compiled/ holds compiled entry
scripts when requested. optional-assets/ holds creature/store blueprints. manifest.json records every
output and its hash. There is no module, replacement load handler, or replacement chat handler.

Keep your module in its existing location. Add resources through your normal source/build or
module/override workflow. Check rw_* name collisions in the module, HAKs and overrides. Save the old
versions of anything you change. Matching NWNX headers and binaries are essential.

## A. Existing module initialization

After your normal initialization, add:

```c
ExecuteScript("rw_init", GetModule());
```

Keep the existing handler and its order of operations. These defaults do not register an NWNX Chat
callback or spawn NPCs. rw_init subscribes DM/store events; audit ordering and coexistence with your
existing event subscribers in staging.

## B. Choose exactly one chat route

### Standard module OnPlayerChat

At the point where your existing handler approves the message, call:

```c
ExecuteScript("rw_modulechat", OBJECT_SELF);
```

Run inside the actual event, after filtering/moderation. Skip the call for rejected, hidden, private
or redirected messages. It reads the final event message and handles eligible Talk. Frameworks that
defer/reconstruct chat need developer review where valid speaker/message context is still available.

### Existing NWNX Chat callback

If NWNX Chat is already your authoritative path, call from inside that callback:

```c
ExecuteScript("rw_chat", OBJECT_SELF);
```

Call only after your approval checks. Suppression/skip state is not automatically propagated to this
adapter. Do not call from an ordinary module event or delayed callback with expired NWNX context.
Do not register a second chat callback. Do not install both routes: duplicate ingestion can produce
duplicate messages or requests.

## C. Bind one world-owned NPC

Create a dashboard profile named `test_guard` (stable ID). After your world creates/loads its creature:

```c
SetLocalString(oNPC, "rw_profile", "test_guard");
ExecuteScript("rw_bind", oNPC);
```

New bindings start paused. Resume from the dashboard. Binding hooks Talk To and retains the previous
dialogue handler for fallback: test this with your own dialogue/conversation system. Binding does not
replace the existing creature's location or inventory. The current bridge supports 32 bound NPCs.

Before your world despawns, pools, repurposes or reassigns that creature:

```c
ExecuteScript("rw_unbind", oNPC);
```

Bind again on the normal respawn/load path. Stable IDs retain memories. Do not bind two simultaneously
live creatures to the same profile ID.

## D. Optional features

World-owned spawning/persistence remains the default. The example companion config disables
allow_dm_spawn and allow_persistent_spawn. Enable them only after designing coexistence with your
world's persistence system.

Basic conversation needs no demo blueprints. For shops, install optional-assets/rw_shop.utm and test
store events against your transaction scripts. For Role Weaver creature creation, also supply
rw_base.utc and review the creature-build requirements. All selected actions remain game-validated.

## E. Redis and plugin configuration

Keep your server launcher and existing plugins. Ensure Chat, Events, Redis, Creature and Player are
enabled on a matching Core/server build. Point NWNX Redis to the same loopback port as the companion.
Do not change a Redis endpoint used by other systems without coordinating their configuration.
This Python transport does not support Redis authentication, TLS or remote hosts.

## F. Staging and rollback

Use your normal staging deployment/restart process. Verify existing chat behavior first, then binding,
DM takeover, filtering, world despawn/respawn, merchant coexistence if enabled, and companion outages.

To revert, remove the added hook calls and restore original handler sources/binaries. Remove only
resources from the manifest that you installed. Unbind test NPCs first if practical, then restart NWN
to clear callbacks. Stop the companion separately. Keep application and campaign-data backups.
Never flush a shared Redis database or remove shared plugins.
