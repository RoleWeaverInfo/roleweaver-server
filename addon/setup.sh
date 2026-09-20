#!/usr/bin/env bash
# Run from any directory: bash addon/setup.sh prepare
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ACTION="${1:-help}"
if [[ "$ACTION" == "environment" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements-guardrails.txt"
  echo "Python environment ready. Next: bash addon/setup.sh check"
  exit 0
fi
if [[ "$ACTION" == "help" ]]; then
  echo "Edit addon/setup.json, then run:"
  echo "  bash addon/setup.sh environment  # create Python environment"
  echo "  bash addon/setup.sh check        # check Redis and companion prerequisites"
  echo "  bash addon/setup.sh prepare      # build Aurora import; no server changes"
  echo "  bash addon/setup.sh install      # install/start companion only"
  echo "  bash addon/setup.sh restart      # restart companion only"
  echo "  bash addon/setup.sh status"
  exit 0
fi
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "First run: bash addon/setup.sh environment" >&2
  exit 1
fi
shift
exec "$ROOT/.venv/bin/python" "$ROOT/tools/setup_addon.py" "$ACTION" "$@"
