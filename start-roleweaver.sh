#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
umask 077
mkdir -p .local
test -f .local/config.json || cp config.example.json .local/config.json
exec python3 -m roleweaver.web --config .local/config.json
