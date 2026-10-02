# Security, permissions and resource limits

Focused release review: 2 October 2026. This records the current trust boundaries,
changes and verification; it is not an independent penetration test or a player-capacity guarantee.

## Deployment boundary

The dashboard is an administrator interface, bound to `127.0.0.1`, protected by
one shared administrator password. The initial password is **roleweaver**;
[change it on the server](DASHBOARD_LOGIN.md) before sharing access. It has no
individual accounts or player roles. A signed-in administrator can access database
exports and world controls. Use a dedicated,
trusted OS account and an SSH tunnel; do not publish the port through a public
proxy or router. Redis must also remain private to the trusted server processes.
An untrusted local process is outside this isolation boundary.

The HTTP handler checks the exact local Host/port, Origin and browser fetch
metadata. Duplicate headers and cross-site requests are refused. CLI clients
without an Origin still work locally. These checks reduce browser-origin attacks;
they complement the password/session gate. Use the same local and remote dashboard
port in an SSH tunnel so the Host check succeeds.

Provider keys are stored separately from public settings, written atomically with
private permissions, and masked in status responses. HTTPS provider redirects
are refused. OpenAI/Gemini use fixed endpoints; LM Studio endpoints are limited
to local/private addresses. Filtered support reports exclude credentials, prompts,
conversations and database contents. Full recovery backups contain private game
data and should be treated differently from support reports.

## Authority stays in the game scripts

Reviewed companion ownership, DM action permissions, exchange/payment handling,
NPC combat, stale commands and encounter scope. An LLM reply can propose only
supported actions. Game scripts recheck ownership, current permissions, object
identity, range, session/command freshness and relevant combat or possession state
before acting. Player payment offers require confirmation and balance validation;
dialogue alone cannot transfer gold. Companions require server permission and
player opt-in, and another player's companion cannot be controlled through chat.

Prompt-injection screening and lore isolation complement these checks. They do
not guarantee correct or in-character model output. Do not put credentials or
out-of-game private information in lore, profiles or dialogue.

## Limits and overload behaviour

| Resource | Default / hard bound | What happens at the limit |
| --- | --- | --- |
| Dashboard connections | 16 active connections; listen backlog 16 | Excess connections close promptly instead of creating another thread |
| Dashboard login | 10 attempts/minute, 1 password check at a time; 32 sessions, each up to 12 hours | Login attempts are refused temporarily; expired sessions must sign in again |
| HTTP uploads | 10-second socket inactivity timeout; 20-second ordinary body deadline | Incomplete/slow requests stop; malformed framing is rejected |
| Ordinary JSON request | 64 KiB; larger existing limits only for lore/backup routes | Oversized requests are rejected before reading the body |
| Database recovery upload | One at a time, up to 512 MiB, 300-second body deadline | A second upload is refused; failed temporary uploads are removed |
| AI worker pool | 4 running workers; 8 unfinished jobs total | New work is refused; NPC/check-in/director busy flags are released |
| Provider calls | 4 concurrent attempts across the service | New attempts fail promptly without waiting in another queue |
| Provider rate | 180 actual attempts per rolling minute | Further attempts fail locally until capacity becomes available |
| Provider request body | 512 KiB | Rejected before contacting the provider |
| Dialogue budget | 6 per player/minute, 60 globally/minute | Existing dialogue admission limits apply before generation |
| Translation | 1 worker, queue 64, default 6 requests/minute | Original text remains usable; cached translations are reused |
| Companion character exports | Dirty changes coalesce over 600 seconds | Inspection/chat does not trigger exports; logout flushes pending changes |

The provider limit covers dialogue, safeguard reviews, AI-DM requests, translations,
connection tests, model-list requests and each Gemini fallback attempt. Failed
outbound attempts also count. Changing provider/model does not reset the counters;
restarting the service does. One dialogue turn may use several attempts.

The limits belong to one running Role Weaver service. Separate worlds/services
using the same API account do not share them. They limit work, not spending;
provider-side quotas and budgets remain useful. Usage & Performance shows token
and estimated-cost information. Health & Support shows concurrent requests,
attempts in the last minute, refused requests and worker capacity.

To tune the shared limits, edit the installed world's `config.json`, retaining its
other settings, then restart the Role Weaver service:

```json
"provider_max_concurrent": 4,
"provider_attempts_per_minute": 180
```

Allowed ranges are 1–8 concurrent and 1–600 attempts/minute. Start lower for a small
local model or a constrained API quota. Increasing limits does not make the game
or provider faster. Existing feature-specific budgets still apply. This change
does not require restarting NWN. The companion save interval is separately
documented in [Companions](COMPANIONS.md).

HTTP header timeouts and provider socket timeouts are inactivity timeouts, not
absolute deadlines for every possible trickle of data. Concurrent work is bounded;
this does not turn the dashboard into an internet-facing server. Translation and
world databases can grow as new content/players are encountered; monitor disk space
and backup retention in Health & Support and Database & Recovery.

## Changes and verification

This review added bounded HTTP connections, explicit upload deadlines, strict
request framing, exclusive recovery uploads, a bounded AI work queue and a shared
provider limiter. Rejected work now releases its domain-specific busy flags.

The subsequent [dashboard-login update](DASHBOARD_LOGIN.md) adds a shared password,
hashed server-side credentials, revocable sessions and rate-limited login attempts.
Its full Ubuntu suite passed 612 tests, including protected recovery/API routes and
authenticated installer readiness checks. Browser sign-in and logout were also
verified against the installed service.

An audit of the installed optional-Guardrails environment found PyJWT 2.14.0 affected
by [GHSA-42vr-xj54-vc7v](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v).
The requirements now require PyJWT 2.15.0 or later within version 2. The reviewed
application does not expose a JWT authentication endpoint; the dependency update
is precautionary hardening. Reinstall `requirements-guardrails.txt` with the
service's Python interpreter when updating an existing Guardrails environment.

Verification performed:

- Full Ubuntu/Python 3.12 suite with Guardrails and PyJWT 2.15.0: 602 tests passed.
- Adversarial HTTP tests: cross-site/duplicate headers, ambiguous lengths,
  invalid JSON shape, truncated/timed uploads and bounded socket handlers.
- Worker/provider tests: concurrent admission, failed-attempt accounting,
  fallback limits, settings changes and recovery after rejected work.
- Updated dependency inventory: 109 packages checked by `pip-audit`, no known
  advisories reported at review time. This covers the Python environment, not
  the operating system, NWN binaries or NWNX plugins.
- Black formatting, dashboard JavaScript syntax and draft-recovery checks.

Provider responses in automated tests are mocked; no API credentials or real
billing calls are needed. Existing game permission checks were reviewed, not
revalidated through a new multi-player gameplay session during this review.
Real-world load testing, a fresh third-party installation and independent security
review remain separate release evidence. Repeat the dependency audit before
publishing because advisories and dependency resolution can change.
