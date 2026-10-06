# Role Weaver Server Add-on

A Linux service connecting AI NPCs, an AI DM encounter assistant and cached
world-text translation to **Neverwinter Nights: Enhanced Edition servers running
NWNX:EE**. It runs alongside your game server. Server owners and DMs use its browser
dashboard; players interact through the normal NWN:EE client.

## Choose a download

**Version 1.0.0** — [Release, downloads and checksums](https://github.com/RoleWeaverInfo/roleweaver-server/releases/tag/v1.0.0).

| Package | Purpose | Instructions |
| --- | --- | --- |
| [RoleWeaver-Demo-1.0.0.tar.gz](https://github.com/RoleWeaverInfo/roleweaver-server/releases/download/v1.0.0/RoleWeaver-Demo-1.0.0.tar.gz) | Explore the editable demo before integrating your server | [Demo setup](START_DEMO.md) |
| [RoleWeaver-Server-Addon-1.0.0.tar.gz](https://github.com/RoleWeaverInfo/roleweaver-server/releases/download/v1.0.0/RoleWeaver-Server-Addon-1.0.0.tar.gz) | Install alongside your existing NWN/NWNX world | [Server add-on setup](START_ADDON.md) |

Each download has its own **START_HERE.md** and **`bash setup.sh`** launcher.
The Server Add-on also includes a localhost graphical installer: run
**`bash setup.sh gui`** on Linux and use its printed SSH-tunnel URL from Windows.
The demo includes Crown Hall, forest robbery and cave hostage encounters, the
caravan investigation, Royal Guide, merchants and authored character lore.
Fresh instances contain no previous conversations, memories, player profiles or
translation cache. Developer installation databases are never shipped.

The reference environment is **Ubuntu 24.04 x86-64 / Python 3.12**.
NWN dedicated-server files, matching NWNX plugins/headers, Redis and a compiler
are separate dependencies. Guides cover installation and reuse of existing folders.
This is not a native Windows server package; players use their usual NWN:EE client.

## Features

- **AI NPCs:** personalities, persistent memories, scoped lore, perception,
  approved movement, patrols, NPC visits, inventory tasks and assistance.
- **DM control:** pause/resume, possession priority, spawning, movement and persistence.
- **Merchants:** real stock and prices, shop access, configurable haggling and
  game-validated payment/exchange requests.
- **AI DM encounters:** separate live and persistent panels; proposals, stages,
  outcomes, optional social rolls and bounded automated direction. Live scenes
  last until cleanup or module reset; armed persistent scenes can recover after
  restart. Game scripts validate actions and handle combat.
- **Player familiars:** opt-in chat, commands, remembered identity, inventory/errands
  and visits. Editable personality templates and controls are in [Companions](docs/COMPANIONS.md).
- **Translation:** players choose a language with `/rw language`. Supported world
  text is translated on demand and cached; source changes need a new translation.
  Chat, tells, logs and player names are excluded. Public player descriptions may
  be translated. Independent multiplayer dialogue translation uses the optional
  [native adapter](extensions/nwnx_translation/README.md).
- **Administration:** OpenAI, Gemini and LM Studio; safeguards; knowledge inspection;
  token, latency and estimated-cost monitoring; translation diagnostics; verified
  database recovery; filtered health/support reports.

The dashboard initially uses password **roleweaver**, settable on the server.
Keep it and Redis private; use SSH for remote access. See [Dashboard login](docs/DASHBOARD_LOGIN.md)
and [security/limits](docs/SECURITY_AND_LIMITS.md). Dialogue and translation need a
configured provider or local model. Costs, availability and model behavior vary.

## Documentation and feedback

- [Documentation index](docs/README.md), [release notes](docs/releases/1.0.0.md)
- [Demo walkthrough](demo/PLAYTEST.md), [editing the demo](demo/CUSTOMIZE.md)
- [Guided setup and upgrades](docs/GUIDED_SETUP.md)
- [Developer setup](docs/DEVELOPMENT.md), [architecture](docs/ARCHITECTURE.md), [contributing](CONTRIBUTING.md)
- [Packaging](docs/DISTRIBUTIONS.md), [release checklist](docs/RELEASE_CHECKLIST.md), [roadmap](docs/ROADMAP.md)

Test on a staging copy before integrating a modified persistent world.
Report problems in [GitHub Issues](https://github.com/RoleWeaverInfo/roleweaver-server/issues)
with package/runtime versions, NWN/NWNX build, model and reproduction steps.
Use filtered support reports; do not post databases, keys, raw logs or private
conversations. Separate optional model-evaluation notes are for administrators;
they are not part of the in-game walkthrough.

Application and distribution version: **1.0.0**. Source is under the
[MIT license](LICENSE); [asset/third-party notes](THIRD_PARTY_NOTICES.md) apply
separately. Historical documentation remains available through Git history and tags.
