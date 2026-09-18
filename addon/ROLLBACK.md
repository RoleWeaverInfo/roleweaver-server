# Upgrade and rollback

Before installation, back up your module, changed scripts, configuration, overrides and campaign data
using your normal process. Keep the generated manifest and note which resources you installed.

For companion upgrades, stop roleweaver-YOUR_WORLD, run the installer from the new extracted add-on
with the same world ID/target, then run its printed service commands. Configuration/data are preserved
and previous application releases retained. Keep the referenced Python environment available. Review
database/protocol changes before mixing versions; a Python update does not update native scripts.

To remove game integration, remove only added init/chat/spawn/despawn hook calls and recompile the
original handlers. Unbind test NPCs if practical. Restore any replaced resources from your backup and
remove only integration resources listed in the manifest. Restart NWN using your normal procedure to
clear callbacks. Stop/disable the companion separately.

Do not flush Redis, delete unrelated overrides/campaign databases or remove shared NWNX plugins.
Keep application backups if memories will be reused. They do not include the whole NWN world or its
merchant campaign databases.
