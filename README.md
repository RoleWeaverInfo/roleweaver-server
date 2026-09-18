# Role Weaver Server

An AI NPC companion for **Neverwinter Nights: Enhanced Edition** servers using NWNX:EE.
It runs alongside an existing server; it does not replace NWN or its module.

This repository is the developer source baseline derived from the tested **0.26.7** build.
It is preparation for an alpha release, not yet a self-contained demo distribution.

## Start here

- **Contribute code:** [Developer setup](docs/DEVELOPMENT.md), [architecture](docs/ARCHITECTURE.md), [contribution guide](CONTRIBUTING.md).
- **Understand the game connection:** [bridge protocol and authority](docs/GAME_BRIDGE.md).
- **Integrate an existing world:** [integration overview](docs/INTEGRATION.md). Test a copy of your world first; the guided alpha installer is still planned.
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

Game installation files, user worlds, keys, player databases and compiled release bundles are not
included. Source code is covered by the repository's [MIT license](LICENSE); see
[third-party and asset notes](THIRD_PARTY_NOTICES.md) before distributing game assets.
