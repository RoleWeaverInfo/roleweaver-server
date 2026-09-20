# Role Weaver Server

An AI NPC companion for **Neverwinter Nights: Enhanced Edition** servers using NWNX:EE.
It runs alongside an existing server; it does not replace NWN or its module.

## Alpha demo download

[Download Demo Alpha 0.1.0](https://github.com/RoleWeaverInfo/roleweaver-server/releases/tag/v0.1.0-alpha.1)

Explore the Kingdom of Role Weaver, meet its inhabitants, shop and haggle, and solve a caravan investigation through conversation. Personal NPC memories persist between visits; the investigation resets each login.

- **Play the demo:** download `RoleWeaver-Demo-Alpha-0.1.0.tar.gz`, extract it on Linux and open its START_HERE.md. [Read the demo guide](START_DEMO.md).
- **Integrate your own server:** the source includes a separate add-on installer, editable setup files and an Aurora import generator. Follow [START_ADDON.md](START_ADDON.md) on a staging world first.
- **Help test:** try the [playtest checklist](demo/PLAYTEST.md) and [conversation/guardrail model comparisons](demo/LLM_COMPARISON.md). Report results in [Issues](https://github.com/RoleWeaverInfo/roleweaver-server/issues), including the model, settings and reproduction steps, without private data or keys.

Ubuntu 24.04 is the tested server environment. Players use the normal NWN:EE client. Generated dialogue requires a configured provider or local model; provider charges and limits may apply.

The application derives from runtime **0.26.7**; **Alpha 0.1.0** identifies the distribution. See the [release notes](docs/releases/alpha-0.1.0.md) for known limitations.

See [distribution contents and release packaging](docs/DISTRIBUTIONS.md).
NWN/NWNX/compiler dependencies are supplied separately.

## Start here

- **Contribute code:** [Developer setup](docs/DEVELOPMENT.md), [architecture](docs/ARCHITECTURE.md), [contribution guide](CONTRIBUTING.md).
- **Understand the game connection:** [bridge protocol and authority](docs/GAME_BRIDGE.md).
- **Integrate an existing world:** [step-by-step add-on setup](START_ADDON.md). Test on staging before your live world.
- **Find feature documentation:** [documentation index](docs/README.md).
- **Plan the alpha:** [release checklist](docs/ALPHA_CHECKLIST.md).

## Current capabilities

Persistent NPC profiles and memories; world and restricted lore; player conversation targeting;
DM pause, takeover and spawning; temporary/persistent placement; approved movement and shop actions;
merchant inventory and bounded haggling; backups; provider settings; safeguards; knowledge inspection;
and token, latency and estimated-cost monitoring.

OpenAI, Gemini and a local LM Studio endpoint are supported. Provider availability and quotas remain
external dependencies. Offline mode allows dashboard development without API credentials.

## Quick developer start (Ubuntu 24.04, Python 3.12)

```bash
git clone https://github.com/RoleWeaverInfo/roleweaver-server.git
cd roleweaver-server
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests
mkdir -p .local
cp config.example.json .local/config.json
python -m roleweaver.web --config .local/config.json
```

Open <http://127.0.0.1:8743>. Without Redis/NWN the dashboard reports a disconnected bridge;
that is expected for this dashboard-only start. See developer setup for optional Guardrails and
native game requirements. The dashboard binds to loopback; use an SSH tunnel for remote access.

## Repository layout

```text
roleweaver/             Python application and static dashboard assets
  services/            Dialogue, NPC lifecycle and world administration
bridge/                NWScript game integration and authoritative checks
tools/                 Module-copy, build and integration utilities
tests/                 Automated regression tests and separate live harnesses
assets/                Small creature/store resources; see asset notes
docs/                  Architecture, setup, feature guides and release checklist
packaging/             Example user-service unit
examples/              Example world binding script
```

The demo includes an editable sample world. Game installation files, private player data and keys are not included. Source code is covered by the repository's [MIT license](LICENSE); see
[third-party and asset notes](THIRD_PARTY_NOTICES.md) before distributing game assets.
