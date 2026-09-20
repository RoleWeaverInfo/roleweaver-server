# Demo alpha validation

Updated September 19, 2026 from runtime 0.26.7.

- 238 application tests pass (10 platform/optional-dependency skips on Windows).
- Ubuntu compiled the edited YourWorld_Fixed investigation and its demo spawn script for the separate rw_demo namespace.
- Both main (UDP 5121/dashboard 8743) and demo (UDP 5125/dashboard 8745) registered all six starting NPCs in auto mode. The King is summoned by the story.
- Source module bytes are identical in both distribution archives and the main server. The demo build preserves non-script resources while rebinding its runtime namespace.
- Main-server conversation messages were retained during deployment. Demo rebuild and content reapplication preserve existing memories and create backups.

This is not a clean-machine installation test or a completed player/DM playtest of the edited layout. Follow PLAYTEST.md to check navigation, investigation, merchant behavior and model/Guardrails quality before publishing.
