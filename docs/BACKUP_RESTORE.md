# Dashboard backup and restore — 0.6.0

Download backup saves a JSON file containing all NPC profiles, shared world lore, curated memories, conversation history and the player identity salt needed to match returning characters. It excludes provider settings, API keys, server passwords, modules and creature placement. Treat backups as private player-history files.

Choose a JSON backup (maximum 32 MB) to validate it and see NPC names and record counts. Restore this backup asks for confirmation and replaces current data. A preview expires after ten minutes and is single-use. Connected NPCs must acknowledge Paused first; release DM possession before restoring. A disconnected known NPC or failed acknowledgement blocks replacement. A failed attempt may leave some NPCs paused.

Before replacement a recovery JSON is saved under the companion data directory as before-restore-<timestamp>.json. Restore is one SQLite transaction. Profiles start paused, credentials remain unchanged, and the world continues owning its creatures. NPCs present only in the previous data have no restored AI profile; creatures are neither created nor destroyed. Resume selected NPCs after reviewing the result. This is replacement, not merge. Edits not saved in the dashboard are not backed up.

Validation: 42 Python tests, isolated HTTP download/preview/restore roundtrip and single-use-token check, dashboard JavaScript syntax check, and live read-only endpoint verification. No restore was performed against user playtest data.
