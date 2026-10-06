#!/usr/bin/env bash
# One entry point; the wizard selects/creates .venv when a Python environment is needed.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python first: sudo apt install python3 python3-venv" >&2
  exit 1
fi
if [[ "${1:-}" == "gui" ]]; then
  shift
  exec python3 "$ROOT/tools/setup_gui.py" "$@"
fi
exec python3 "$ROOT/tools/setup_wizard.py" "$@"
