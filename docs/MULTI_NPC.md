# Multiple world-managed NPCs — 0.4.0 staging



Connect to your configured staging NWN and dashboard ports.

Mira (innkeeper) and Orren (retired caravan guard) are created by the staging world's pw_npcs hook. Both currently use the innkeeper blueprint as a placeholder. The existing James profile is preserved and remains unbound.



Each character starts paused. Select and resume each separately. Use ordinary player Talk near the character, or `Mira: Hello` / `Orren: Hello` when both are nearby. Only one NPC receives a conversation event. Explicit addressing requires proximity and line of sight; an unknown or ambiguous address receives no reply. A colon is reserved for explicit addressing. Without a colon, the nearest living bound NPC within 10 metres is selected (binding order breaks distance ties). Paused or possessed recipients do not receive AI conversation events; speech is never redirected to a different character.



Conversation history and curated memories remain scoped to the NPC and player. NPCs do not automatically overhear each other's conversations. This is conversational interaction; autonomous travel, combat decisions, quest awards and item creation are not implemented.



Validation: 29 Python tests pass, including provider-context separation and pausing one NPC while another reply completes. Native routing checks are recorded in the staging server log as RW_ROUTING_TEST. Human acceptance: tell Mira a fact; ask Orren whether you told him that fact; resume/pause independently; verify possession/release and reconnect persistence.



World integration: adapt examples/pw_npcs.nss to your own spawning system; keep the rw_profile / rw_bind call on world-created creatures. Do not install the staging hook into a live world unchanged.



## Delete NPC

Select a profile and click Delete NPC, then confirm. This permanently removes its profile, transcript, curated memories and saved placements. Connected NPCs are detached after a game acknowledgement; world creatures are not destroyed. A stale game connection must recover before a known bound NPC can be deleted. World spawn hooks remain world-owned; remove or change their rw_profile binding if retiring that identity permanently.
