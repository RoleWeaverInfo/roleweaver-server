# Developer setup

## 1. Choose the scope

The dashboard and regression tests can run without NWN. Native gameplay requires Linux, NWN:EE
server files, NWNX:EE and Redis. Ubuntu 24.04 / Python 3.12 is the current tested baseline; Docker
is not required. Windows can run core Python tests, but native game integration is tested on Linux.

## 2. Create an isolated Python environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests
```

On Windows activate with `.venv\Scripts\Activate.ps1`. The core application uses Python's standard
library. Developer tools and optional Guardrails have separate requirement files.

For the full validation suite:

```bash
python -m pip install -r requirements-guardrails.txt
python -m unittest discover -s tests
```

Without those packages, optional Guardrails tests are skipped; inspect the test summary.
`test_*.py` tests use temporary storage and mocks. `live_*.py` scripts are separate native integration
harnesses: read their arguments and prerequisites before running them.

## 3. Start an offline dashboard

```bash
mkdir -p .local
cp config.example.json .local/config.json
python -m roleweaver.web --config .local/config.json
```

Open http://127.0.0.1:8743. Data is stored next to the configuration in `.local/data/`.
The bridge will show disconnected without Redis and an integrated game world. This does not mean
that the dashboard failed. Stop with Ctrl+C. No credentials are required for offline mode.

For a local Redis process on Ubuntu, install/start your Redis package and keep it bound to loopback.
Use a unique `world_id` and `redis_prefix` per world; never point development at a live world's queue.
Configure online providers in the dashboard. Do not add keys to the example config or source tree.

## 4. Native game development

The repository does not include the NWN runtime, NWNX shared libraries, compiler, or YourWorld.mod.
Obtain a compatible NWN:EE dedicated server and matching NWNX:EE plugins/headers independently.
The current build helper expects an executable `tools/nwnsc` and a native runtime directory.
Run `python tools/build_addon.py --help` for its arguments and read [integration](INTEGRATION.md).
The helper builds a review bundle, not an automatic production deployment.

Before installing any compiled scripts, back up your module, override scripts, configuration and
campaign databases. Preserve your world's load/chat handlers. Use a separate NWN port and Redis
prefix for the test world. Do not copy compiled scripts into a running production module.

## 5. Format and validate

```bash
python -m black roleweaver tools tests
python -m black --check roleweaver tools tests
python -m unittest discover -s tests
```

CI runs the core and optional-Guardrails configurations on Ubuntu/Python 3.12. Native playtests are
manual and are not implied by a green CI run. See [testing](TESTING.md).
