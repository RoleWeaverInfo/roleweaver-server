# Editing the investigation demo

The world is ready for a fresh playthrough. The lore refresh keeps your existing
NPC names, appearances, modes, shops, permissions and placements. It does not
rebuild the hall.

## Arrange the world

1. Connect as DM to the test server on `192.168.167.128:5121`. Walk around and decide where each NPC and landmark should go.
2. Use the dashboard's NPC movement controls for the persistent innkeeper and merchant. These two creatures are restored from Role Weaver's saved placements; they are not placed creatures inside this module file. Ordinary DM possession/movement is useful for previewing a position, but should not be assumed to save it permanently. Resume AUTO mode when finished testing.
3. Open the supplied `YourWorld_Fixed.mod` copy in the Aurora Toolset to move the board, throne, other placeables and the module-placed guard, wizard, cleric and Holt. Save your edited copy. Editing while the server runs does not change the loaded area.
4. Keep the area resource name `throne_room`, the object tags, `rw_id` locals and installed event scripts. The board uses `rq_board`; the existing throne uses `rq_throne`. Move these objects rather than replacing them with untagged copies. The King walks to the throne object but currently enters at a scripted position (25, 20); leave that arrival point clear or have the entry script updated.
5. After moving landmarks, recapture the corresponding approved movement destinations in the dashboard. These are stored coordinates, so moving a table or shrine in the Toolset does not automatically move its destination. The current interface may require removing that destination from NPC permissions, deleting/recreating it, and granting it again. Ask for help updating them together if needed.
6. Once your edited module is ready, stop the test game server, back up the existing module, replace `~/nwn-world/modules/YourWorld_Fixed.mod`, and restart. The companion stores lore, profiles and persistent placements separately; a module replacement should not erase them. We can handle this coordinated install after your editing.

## Change the story

`content.json` is the editable authored source. `lore/` contains one readable
Markdown copy per document. Keep both in sync. Public documents are common
knowledge; NPC-specific documents hold personal histories and private testimony.
The dashboard lets you edit these during play too. Before an alpha package is
built, export or copy your final dashboard edits back into this source so a fresh
installation gets the same content.

For a content-only refresh, stop the companion and run `refresh_content.py` with
its `--source` and `--database` paths. It creates a SQLite backup before updating
personalities, voices and lore. It preserves placements and settings. Do not run
`seed.py` or the initial module builder after arranging the world: those tools
restore the original demo defaults.

## Replaying the investigation

Log out and reconnect. Appointment, collected clues and completion restart for
that player only. NPCs keep their conversations and personal memories of the
player; old testimony is labelled as an earlier visit rather than current case
evidence. Other connected players' investigations are unaffected.

The small demo allows one 100-gold reward per visit. Reconnecting does not remove
previously earned gold. No database deletion or conversation clearing is needed.
Do not use `--reset-player-history` for a story reset: that optional authoring
cleanup erases personal history and is separate from normal demo replay.

## Before an alpha release

After layout editing, test a full investigation with a fresh character, NPC
movement, merchant prices and haggling, persistence after restart, and several
LLM providers. Capture the final module, profiles, lore, placements and shop
setup together. Build fresh demo data from those authored sources rather than
shipping a copy of the test server's data directory. Keep API keys, player
conversations, identity records, logs, campaign saves and private backups out of
the release. Release preparation comes after this editing/playtest pass.
