# Game bridge and authority

The companion and NWNX bridge exchange JSON on world-specific Redis queues:
`<redis_prefix>:events` from game to Python and `<redis_prefix>:commands` in the other direction.
Use different prefixes for different worlds. Redis is an internal transport, not a public API.

## Follow the code

- `rw_chat*` and `rw_talk*`: player speech, conversation targeting and hearing policy.
- `rw_inc.nss`: common event/identity and state helpers.
- `rw_tick.nss`: command polling, validation, execution and acknowledgements.
- `rw_actions.nss`: approved action execution.
- `rw_merchant.nss`, `rw_stock.nss`, `rw_shop_evt.nss`: stock, customer prices and transactions.
- `rw_possess.nss`: DM control integration.
- `Service.event` / `Service.command`: Python receive/send boundaries.

Commands carry an NPC identity, session, epoch, expiration and request ID. Acknowledgements correlate
by request ID. Never equate queue submission with successful game execution. `say` also carries
listener and conversation revision; merchant quotes can carry a price stamp. The game rejects stale
or inappropriate operations, including speech while possessed, dead or outside hearing range.

## Adding an action

1. Define and validate an owner-authorized action in Python.
2. Expose only approved IDs/destinations in the model's context.
3. Validate the model's selected ID without interpreting arbitrary code or coordinates.
4. Implement the command in NWScript, rechecking current permission, identity and location.
5. Acknowledge success/failure and test stale sessions, DM takeover and invalid targets.

Any bridge/protocol change needs matched Python and compiled scripts. Compile against headers for
the deployed NWNX build. Preserve existing module load/chat events; review generated integration
wrappers and avoid a second conflicting chat registration. See [INTEGRATION.md](INTEGRATION.md).
