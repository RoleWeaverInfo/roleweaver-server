# Contributing

Start with [developer setup](docs/DEVELOPMENT.md) and [architecture](docs/ARCHITECTURE.md).
Use a branch and a pull request. Explain the player or server-owner problem, the resulting behavior,
and the tests performed. Keep mechanical formatting and behavior changes distinguishable in review.

## Working conventions

- Python 3.12 is the tested development baseline. Format with Black using `pyproject.toml`.
- Prefer small functions and explicit names. Document public responsibilities and invariants.
- Comments should explain a constraint or decision, not translate each line into English.
- Put dialogue work in `services/dialogue.py`, NPC lifecycle in `services/npcs.py`, and world
  administration in `services/world.py`. `service.py` owns shared state and game event dispatch.
- Keep provider HTTP code independent of game mutation. Game commands must go through the
  service queue and be validated again by NWScript.
- Do not hold the service lock during an LLM network request.
- Keep settings and backup compatibility explicit. Add migration tests when formats change.
- Preserve existing import entry points (`roleweaver.service.Service`, `roleweaver.web`).

## Before submitting

```bash
python -m black --check roleweaver tools tests demo
python -m unittest discover -s tests
```

Run the optional Guardrails suite when changing validation. For bridge changes, compile with the
matching NWNX headers and exercise the relevant live harness on an isolated world. Unit tests alone
do not prove native behavior. Never run a live harness on a production world.

Do not commit API keys, provider.env, real configuration, identity salts, chat histories, database
files, native server installations or game modules. Give synthetic examples in bug reports. Include
version, platform, reproduction steps and redacted error types, not a raw private data directory.

## Current priorities

The alpha checklist tracks guided setup, demo packaging, diagnostics export and clean-machine
validation. Discuss large architectural changes before replacing the shared-state service design.
