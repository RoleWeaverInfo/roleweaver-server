# Existing-server acceptance tests

Use staging, a backup and one test NPC. Record versions, provider/model and settings; never publish keys
or unredacted player conversations.

1. Before integration, verify login, chat moderation, private channels, spawning and stores.
2. Install the reviewed bridge, start the companion, and run tools/check_addon.py.
3. Bind/resume one NPC. Offline Talk should reach it; unrelated conversations should not.
4. Verify rejected, muted and hidden messages never reach Role Weaver's conversation view.
5. Configure/test an LLM and check ordinary conversation and memory.
6. Possess/reserve/pause the NPC during a slow request. Stale AI output must not override DM control.
7. Exercise your own despawn/respawn/pooling path. Check unbind/rebind and duplicate IDs.
8. Restart staging NWN normally. Verify original scripts still run and the bridge reconnects.
9. Stop the companion; the world's existing systems should still work. Restart and test recovery.
10. If enabling shops/actions, test unauthorized-action rejection, purchases, price consistency and
    custom store-handler coexistence before rollout.
11. Exercise rollback before production installation.

Use synthetic prompts for model comparisons. A timeout, quota error or unavailable safeguard review
is not evidence of a successful safety block. Keep model settings, lore and conversation history the
same across comparisons and record actual fallback models from Usage.
