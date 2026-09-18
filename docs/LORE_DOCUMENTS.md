# World documents and lore switches — 0.16.0

## World Lore

1. Open World Lore. Existing world knowledge is preserved as the active **World lore** document.
2. Click **New document**, enter a title and paste/write the text, then **Save document**. Or select one or more UTF-8 `.txt` / `.md` files under **Import text documents**. Word/PDF documents should be exported as plain text first.
3. New and imported documents start **inactive**. Check **Active** beside each document to use it. The checkbox saves immediately; no further Save is needed for a toggle.
4. Use **Edit** and **Save document** to change content. Editing an inactive document does not reactivate it. **Delete** removes the saved document; turning it off keeps it available for later.

Up to 100 documents may be stored, each at most 20,000 characters. Active documents share the existing 20,000-character World Lore prompt budget, including headings when more than one is active. The page shows the current usage; excess activation is rejected without silently truncating sources. Imports are plain text, not executed or rendered as HTML. Multiple-file imports report how many succeeded if a later file fails.

## Lore Access

Each existing entry now has an **Active** checkbox. Unchecking it excludes the entry from new AI prompts and lore checks while retaining its text and audience. Editing does not change its active state. Checked entries still obey public/faction/NPC/DM-only permissions; active DM-only notes never reach AI prompts.

## What switching off means

Inactive sources are excluded from future prompt context and AI lore-checking sources. Older in-progress replies are discarded when sources change. This does not erase facts already present in conversation history or DM-curated memories. For sensitive secrets use DM-only permissions rather than relying on deactivation after disclosure.

## Recovery

Backup format 5 includes every document, including inactive ones, and each Lore Access entry's active state. Manual and automatic recovery backups use this format. Older formats 1–4 remain readable: their single world-lore field becomes one active document, and entries lacking an active flag default to active. Per-document browser draft recovery is retained; the original World Lore draft key remains compatible.
