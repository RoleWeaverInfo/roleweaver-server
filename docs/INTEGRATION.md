# Adding Role Weaver to an established persistent world

Role Weaver is a companion service plus an NWNX script bridge. It does not replace
the world's NWN server, module, database or existing NPC systems. The separate
development server scripts in this source tree are test tools, not deployment requirements.

## Conservative defaults

- The world owns spawning, despawning, movement and persistence.
- Role Weaver handles personality, conversational memory, replies and DM priority.
- Automatic restoration and the `!rw spawn` command are disabled inside the game.
- The service also refuses automatic restoration unless explicitly configured for it.
- The existing NWNX Chat owner remains in control. Registration is manual by default.
- There is no automatic NPC seed in an add-on bundle.

The administrator can explicitly select Role Weaver-owned placements for a world
that wants that feature. Both generated bridge settings and service configuration
must agree. Old placement records are retained when ownership changes, but are not
used to move or recreate characters in world-managed mode.

## Build a review bundle on Linux

Run the builder from the Role Weaver application folder. Keep its inputs and output
inside that folder, using this layout:

```text
RoleWeaver-Addon/
  tools/
    build_addon.py
    nwnsc                 Linux NWScript compiler
  modules/
    YourWorld.mod         Copy of the world's module
  scripts/                Copies of the world's extra NSS/NCS scripts (optional)
  native/
    runtime/              NWN runtime resources, including data/*.key and *.bif
    nwscripts/            NWNX include files, such as nwnx_chat.nss
  builds/                 Generated review bundles
```

`modules/`, `scripts/`, and `native/` are input folders you populate; the source
archive does not include your game files or the compiler. `native/runtime` and
`native/nwscripts` can be copies or symbolic links to the corresponding folders
in your existing installation. They are compiler dependencies, not another server
to install or run. Do not move files out of the running world's installation.

Supply or link the compiler and matching runtime/header folders from your own installed dependencies.
Do not reuse paths from somebody else's test installation.
The builder checks dependencies before creating output and reports missing inputs.

Open a terminal in the Role Weaver folder (the one containing `tools`), then run:

```bash
python3 tools/build_addon.py \
  --module modules/YourWorld.mod \
  --native native \
  --world-id your_world \
  --redis-prefix roleweaver:your_world \
  --scripts scripts \
  --output builds/your_world-review-01
```

Replace `YourWorld.mod` with your copied module's filename; quote the path if it
contains spaces, for example `--module "modules/My World.mod"`. Replace `your_world`
with a stable ID for that world, using the same ID in the Redis prefix and bundle
name. All paths in this example are relative to the Role Weaver folder.

Omit `--scripts scripts` if you have no extra script sources to inspect. The optional
`--scripts` argument can be repeated for additional folders. The builder creates the
output directory; use a new name such as `your_world-review-02` for the next build.
The original module, server configuration and running processes are never modified.
The bundle contains an audit, generated source, compiled bridge, optional revised
module copy, service config example, checksummed file manifest, and rollback steps.
Keep module-containing bundles private unless you have permission to distribute the world.

Static inspection reports module event handlers, possible NWNX Chat registration
in NSS/NCS resources, and reserved resource collisions. It cannot establish every
runtime path or inspect HAK contents automatically. Review overrides, HAKs, scripts
that register handlers later, and custom plugins separately. A clean scan is not
proof of compatibility. Name collisions stop bundle generation rather than overwrite
another integration. Exclusive chat mode refuses detected existing registrations.

## Hook into the world's code

For a world using the standard module OnPlayerChat event (including the tested DMFI
starter module), build with `--chat-mode module`. The revised module calls the
original OnPlayerChat script first, then the new `rw_modulechat` adapter. The adapter
reads the resulting message, ignores empty/suppressed messages, and captures only
eligible Talk. This mode does not register an NWNX Chat callback. Stage the supplied
revised module and compiled scripts; no separate NWNX chat hook is needed in this mode.
It preserves the existing load handler as described below. Custom frameworks that
route or defer chat outside the module event still require administrator review.

After the world's normal module initialization, run:

```c
ExecuteScript("rw_init", GetModule());
```

The optional module copy calls the original OnModuleLoad script before rw_init;
it leaves the other module handlers unchanged. Administrators maintaining source
should integrate that one call into their existing build instead.

Keep the world's existing NWNX Chat callback. After its filtering/moderation and
privacy decisions, explicitly invoke Role Weaver where appropriate:

```c
ExecuteScript("rw_chat", OBJECT_SELF);
```

This call must run inside the NWNX Chat callback so channel/speaker/message getters
have the correct context. Do not put it into an ordinary OnPlayerChat handler.
Use `rw_modulechat` for the standard module event instead; the two adapters share
the same NPC dialogue and DM-control rules. Install only one chat ingestion path.
Do not call it for suppressed messages: skip state is not automatically propagated
to this adapter. Existing chat processing order is an administrator decision.
If no NWNX chat owner exists, --chat-mode exclusive generates a bridge that registers
its own callback. It is an explicit ownership declaration, not automatic discovery.

After the world creates or loads an NPC, bind its stable profile ID:

```c
SetLocalString(oNPC, "rw_profile", "mira");
ExecuteScript("rw_bind", oNPC);
```

Create that ID in the Role Weaver dashboard first. Bindings start paused. Before
despawning or repurposing the creature, call ExecuteScript("rw_unbind", oNPC).
Freed binding slots can be reused; the limit is 32 concurrent NPCs. In world-managed
mode, bind again when the world reloads or respawns the creature. No inventory,
location or creature state is overwritten by this binding operation.

## Companion service

Run the Python service alongside the existing native Linux NWN/NWNX process.
It needs the installed Chat, Events and Redis plugins and a local Redis connection.
Give each world a separate Role Weaver data directory and Redis namespace; use the
same namespace in its generated bridge and service config. Keep the stable world ID
unchanged across ordinary restarts. No Docker is required.

Use the bundle's service-config.example.json as the starting point. Set the AI provider,
model, private environment file and dashboard port for that deployment. The dashboard
is loopback-only and currently assumes trusted local OS access or an SSH tunnel; it
does not yet provide multiple remote DM accounts or role-based permissions.

A user-service example is supplied in packaging/roleweaver-addon.service. It expects
the application at ~/RoleWeaver-Addon; edit the paths for another installation.
Use the generated config as config.json, set an unused web_port if another dashboard
already runs on this host, and put the API key in provider.env with permissions 600.
Install the unit under ~/.config/systemd/user, run systemctl --user daemon-reload,
then systemctl --user start roleweaver-addon. This starts only the companion app;
it neither starts nor restarts NWN. Automatic start at login is an administrator choice.

## Staging and removal

Verify existing chat features first, then NPC binding, remembered dialogue, actual DM
possession, world-owned despawn/respawn, and module restart behavior. Test service
failure too: it must not prevent the world's existing scripts from running.

To remove Role Weaver, remove the added load/chat/spawn calls, restore the original
module if using the supplied copy, remove only the bridge files you installed, and
restart the game to clear NWNX subscriptions. Stop the companion service. Keep its
SQLite data if memories may be needed later, and leave shared Redis installations alone.

This is an administrator integration toolkit. Automatic HAK merging, arbitrary PW
framework adapters, and remote multi-DM administration are not implemented.
