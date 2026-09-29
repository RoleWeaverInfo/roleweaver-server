# Health and support

Open **World administration → Health & Support**. The same panel is available at
`http://127.0.0.1:8743/health` on a standard installation. Use your configured
dashboard port or SSH tunnel address if different. It remains available when the
application databases cannot open; the Role Weaver Addon service must still be running.

## Reading the panel

- **Role Weaver Addon:** available, in maintenance, or unable to open its data.
- **Redis:** an independent, read-only PING. A successful PING does not prove the
  NWN server is running or using the correct world ID and Redis prefix.
- **NWN game bridge:** age of the last matching-world heartbeat, loaded plugins
  and protocol compatibility. No heartbeat is expected while NWN is stopped.
  When it should be running, check its launcher, module hooks and bridge settings.
- **Workers:** bridge/translation thread liveness, active replies and commands
  awaiting game confirmation. Thread liveness does not prove forward progress.
- **Translation cache:** queue, cache hits since startup and ready/pending/failed
  entry counts. Failed entries remain visible until retried; original text is
  still available in game.
- **LLM requests:** observed attempts, failures and average response time during
  the last hour, plus the last request result. Failed fallback attempts count as
  failures even when another model subsequently succeeds. Idle providers are
  shown as untested. The health monitor never calls a model or spends API tokens.
- **Databases:** most recent startup/scheduled integrity checks and checked file
  sizes. These are not a fresh integrity scan every five seconds. Use **Database
  & Recovery → Check integrity** for an explicit check.
- **Recovery backups and disk:** verified snapshot count, latest age, automatic
  backup status and available space compared with the configured reserve.

The monitor samples every five seconds. The browser refreshes while this panel
is visible. A slow or blocked probe is reported as stale after fifteen seconds.

## Enabling game-side health reporting

The current bridge adds `rw_health.nss` to `rw_tick.nss`. Prepare/compile the bridge
with the normal add-on tools, install the updated compiled scripts and restart
NWN during a maintenance window. No module layout changes are required. An older
bridge remains usable but reports that plugin evidence is unavailable.

The heartbeat reports Core, Chat, Events, Redis, Creature, Player and Item for
the full NPC feature set. When translation is enabled, the panel additionally
checks Dialog, Util and RWTranslation and the adapter's protocol. Missing optional
translation plugins do not make the NPC-only bridge unhealthy.

Plugin observations are retained but marked stale when the game disconnects.
Loaded plugins and matching protocols do not prove engine ABI compatibility,
correct installation of every event hook, or successful gameplay actions. Record
the actual NWN/NWNX build versions with a bug report; they are not inferred from
library filenames or the Python package version.

## Downloading a support report

1. Open **Health & Support** and wait for a sample.
2. Select **Download support report**.
3. Review the three files in `roleweaver-support.zip` before sharing it.
4. Include what you were doing, expected/actual behavior, approximate time, and
   your NWN/NWNX versions. Share it with your issue report or support contact.

The ZIP contains `health.json`, `errors.jsonl` and `README.txt`. It includes
application/Python/SQLite versions, a hash identifying the application source,
component states and counts. Error records include a fixed event code, exception
type, optional HTTP status and project-relative Python source locations.

Reports exclude API keys, credentials, addresses, world/player/NPC identifiers,
conversations, lore, prompts, source or translated text, database contents and raw
configuration/engine logs. Exception messages, source lines and local variables
are intentionally omitted. This also means a report may not explain the exact
bad input; support may ask for a small, manually reviewed reproduction example.
Downloading does not upload anything or contact an LLM.

## Log retention and implementation

Filtered errors live in `data/logs/errors.jsonl` and `errors.1.jsonl` through
`errors.3.jsonl`, beside the databases. Each file is limited to 1 MiB. Linux files
are owner-only. Repeated identical event/type/phase/status combinations are written
at most once per minute; a later record includes the accumulated repeat count.
The panel also shows counters since startup and the most recent 20 events in
memory. A restart can discard pending coalesced repeats. This is a diagnostic
history, not a complete audit trail.

The ZIP includes at most 1,000 saved records, rechecked against the allowlist, plus
recent in-memory events in `health.json`. A log write failure cannot stop gameplay;
it appears in the panel. Engine/native crashes outside Python require separately
reviewed NWNX logs. Existing journal output is not imported into support reports.

`health.py` owns sampling and ZIP creation; `health_web.py` owns the independent
HTTP surface; `diagnostics_log.py` owns filtering, coalescing and rotation.
`RecoveryRuntime` owns their lifetime. Application probes hold a recovery lease,
so a restore drains them before replacing files. The log is outside the database
restore set. Do not add arbitrary message fields or raw exception text to it.

Run `python -m unittest tests.test_health tests.test_recovery_http` for the focused
tests. The native dialogue fixture also checks actual loaded/missing plugin
reporting and the translation adapter protocol in an isolated NWN process.
