# Optional example world

The distribution includes `YourWorld_Fixed.mod`: the edited Crown Hall investigation module, identical to the demo source. `content.json` contains its public lore, character profiles and approved destinations. These are examples, not player saves.

For a ready-to-run investigation with its profiles and shop, use the **Demo distribution** and its START_HERE.md. The add-on installer never selects or replaces an existing server module automatically.

This module already contains the Role Weaver hooks and is compiled for world `my_world`, Redis prefix `roleweaver:my_world`. Do not apply the generic unhooked-module builder to it. A different namespace requires recompiling its embedded scripts with matching `rw_settings.nss`. The demo setup does this automatically.

To edit the example, open YourWorld_Fixed.mod in Aurora. Preserve its rq_load, rq_chat, rq_enter and rq_exit module hooks. Keep a backup before editing. The original source in this repository is demo/world/YourWorld_Fixed.mod; release packaging copies it here without changing its bytes.
