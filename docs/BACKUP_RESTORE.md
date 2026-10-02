# Backup and restore

For coordinated world, translation and usage database recovery, use
**Database & Recovery** and follow [the recovery guide](DATABASE_RECOVERY.md).
It includes automatic snapshots and a recovery page that can start when a database
is corrupt.

## Portable JSON backups

The older controls remain below the database recovery panel. **Download backup**
saves profiles, world lore, memories, conversation history, supported world settings,
the player identity salt and persistent NPC placement records. Format 15 also
includes editable familiar templates; companion preferences and dashboard
administration settings are retained. Older backups restore shipped templates. JSON backups exclude
translations, language preferences, usage history, credentials and NWN game files.
They contain private player history; store them securely.

Choose a JSON backup (up to 32 MB) to validate and preview it. The restore token is
single-use and expires after ten minutes. **Restore this backup** replaces current
world data after connected NPCs acknowledge Paused. Release DM possession first.
Failed acknowledgements block replacement and may leave some NPCs paused.

The managed dashboard saves a coordinated ZIP snapshot before JSON replacement;
the world importer also writes before-restore-<timestamp>.json under the data
folder. JSON replacement uses one SQLite transaction. Profiles start paused and
credentials remain unchanged. Restart the NWN module as directed to apply restored
locations. Review and resume NPCs afterward. Unsaved browser edits are not included.

For whole-installation recovery use the ZIP controls, so memories, identity and
translation preferences come from the same recovery point.
