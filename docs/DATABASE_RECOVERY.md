# Database recovery

Open **World administration → Database & Recovery** in the dashboard. This feature
is in the development source; it is not in the published Alpha 0.2.0 packages.

## Save a backup

1. Click **Back up now**. Players may remain connected for a backup.
2. Wait for the operation to finish. The new recovery point should say **Verified**.
3. Select it and click **Download ZIP**. Store a copy on another disk or machine.

Snapshots contain the world database (profiles, lore, memories, encounters and
placement records), translation cache and language preferences, usage history,
and the player identity salt. They exclude API keys, provider settings, server
passwords, module files, HAKs and NWN character/campaign databases. Treat snapshots
as private: they contain conversations and player information. ZIPs are not encrypted.

SQLite saves committed changes as they happen, using WAL and full synchronization.
Backups use SQLite's backup API so committed writes still in the WAL are included.
The companion briefly locks its writers while taking the three database snapshots;
integrity checks and compression run afterward. A backup makes no LLM requests.

## Automatic backups

By default, the dashboard takes a snapshot shortly after startup, then every
15 minutes. It retains 24 recent, 14 daily and 8 weekly points. One file can satisfy
several retention categories. The initial storage budget is 2,048 MB, with 256 MB
of disk space reserved. Change these under **Automatic backup settings**.

Manual, imported and pre-upgrade/pre-restore points start protected. Automatic
rotation removes only obsolete, verified, unprotected points. If protected files
or your selected retention cannot fit the budget, new backups stop and the panel
shows an error. Download and delete unnecessary points or increase the limit.
Unprotect a point before deleting it. The last verified point cannot be deleted
through the dashboard. Archive size is limited to 512 MB compressed / 2 GB expanded.

Scheduled integrity checks also run when automatic snapshots are disabled. A failed
database check pauses the companion and leaves recovery available. A provider or
network failure alone is not treated as database corruption.

## Restore

1. **Stop the NWN game server** with your normal launcher/service. Leave Role Weaver
   running so you can use its dashboard. Wait 30 seconds for its bridge heartbeat
   to expire. Leave Redis running: restore clears this world's buffered bridge
   events and commands so old game activity cannot replay into restored records.
2. In **Database & Recovery**, select a recovery point. If it is on your computer,
   use **Import a recovery ZIP** first; it is validated before being saved.
3. Choose **All databases** or **Translation cache and language preferences only**.
   Translation-only restore preserves current world memories and requires the same
   player identity salt. Only databases listed in the preview will be replaced.
4. Click **Preview restore** and review its date, scope and record counts.
5. Confirm that NWN is stopped, then click **Restore previewed recovery point**.
   Wait until the operation finishes; in-flight LLM requests must drain first.
6. Open the dashboard again, check your data, then start NWN. Players can reopen
   `/rw language` and examine a previously translated object.

Restore replaces data; it does not merge it. Changes after the snapshot are lost.
It also does **not** roll back character inventories, gold or the game world's
campaign database. Coordinate any game-world rollback with your own NWN backups.

Before replacement, Role Weaver creates a protected undo snapshot if the current
databases are healthy. It also copies originals and their WAL/SHM files into
`data/database-quarantine/`. Original files are kept even when corrupt. They are
not automatically pruned or included in the backup storage budget. Keep them until
you have confirmed recovery, then archive/remove that specific quarantine folder.

## If the normal dashboard will not open

Use the **same dashboard address** with `/recovery` appended, for example
`http://127.0.0.1:8743/recovery`. The root page also opens recovery automatically
when database startup fails. Keep your SSH tunnel open as usual.

1. Look at the database health messages.
2. Stop NWN and restore a verified point using the steps above.
3. If you corrected an external problem, such as disk space or file permissions,
   use **Retry companion startup** instead.

Role Weaver never silently deletes a damaged world or creates a replacement empty
world. A restore interrupted while swapping databases is rolled back from the
preserved originals on the next startup. If the originals themselves were corrupt,
the recovery page stays available so you can retry a known good point.

There is no automatic SQLite salvage button: recovering fragments from a corrupt
file can lose records or relationships. When no valid backup exists, preserve the
quarantine and seek manual recovery help. Do not experiment on your only copy.

## Files and older backups

| Location under the companion's data folder | Purpose |
| --- | --- |
| `database-backups/db-*.zip` | Verified database snapshots |
| `database-backups/*.zip.json` | Verification/protection metadata |
| `database-recovery.json` | Recovery settings, outside the databases |
| `database-quarantine/` | Preserved original files from restores |
| `database-restore.json` | Temporary journal for interrupted-restore rollback |
| `.roleweaver.lock` | OS lock preventing a second companion using this folder |

On a standard `my_world` installation the data folder is
`~/.local/share/roleweaver/my_world/data`. A demo has its own instance data folder.
Recovery ZIPs must belong to the configured world ID. Moving an installation also
requires its configuration/credentials, which are deliberately not in the ZIP.

Existing `recovery-backups/*.json` and `translation-backups/*.sqlite3` are preserved.
The new managed dashboard uses coordinated ZIP snapshots instead of the old two
automatic schedules. The legacy JSON download/import controls remain below the new
panel for portable world-data backups; they do not include the translation database.
Use the new ZIP controls for coordinated recovery. Never copy a live SQLite file
by itself while its companion is running.

## Implementation and testing

`db_recovery.py` owns archives, checksums, integrity checks, retention and the restore
journal. `recovery_runtime.py` drains requests and workers before file replacement.
`recovery_web.py` works independently of the application database and uses the same
loopback/origin restrictions as the normal dashboard. Recovery operations run in a
background thread so progress remains visible.

Run `python -m unittest discover -s tests -p 'test_*recovery*.py'` from the repository
root. Tests use disposable worlds for corrupt startup, WAL snapshots, identity
preservation, translation-only restore, interrupted swaps, late worker writes,
retention, disk failures, malformed uploads and HTTP recovery. Never corrupt or
restore a live server merely to test these controls.
