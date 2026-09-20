#!/usr/bin/env bash
# Start a NEW test NWN server. Does not install Role Weaver or change module files.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$HERE/new-server.env"
if [[ ! -f "$CONFIG" ]]; then
  echo "Copy addon/new-server.env.example to addon/new-server.env and edit it first." >&2
  exit 1
fi
source "$CONFIG"
for file in "$NWN_RUNTIME/bin/linux-x86/nwserver-linux" "$WORLD_DIRECTORY/modules/$MODULE_NAME.mod"; do
  [[ -f "$file" ]] || { echo "Missing: $file" >&2; exit 1; }
done
for plugin in Core Chat Events Redis Creature Player; do
  [[ -f "$NWNX_PLUGINS/NWNX_$plugin.so" ]] || { echo "Missing NWNX plugin: NWNX_$plugin.so" >&2; exit 1; }
done
[[ -n "$DM_PASSWORD" ]] || { echo "Set a private DM_PASSWORD in addon/new-server.env first." >&2; exit 1; }
export NWNX_CORE_LOAD_PATH="$NWNX_PLUGINS"
export LD_PRELOAD="$NWNX_PLUGINS/NWNX_Core.so"
export LD_LIBRARY_PATH="$NWNX_PLUGINS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export NWNX_CORE_SKIP_ALL=1
export NWNX_CHAT_SKIP=n NWNX_EVENTS_SKIP=n NWNX_REDIS_SKIP=n
export NWNX_CREATURE_SKIP=n NWNX_PLAYER_SKIP=n
export NWNX_REDIS_HOST=127.0.0.1 NWNX_REDIS_PORT="$REDIS_PORT"
mkdir -p "$WORLD_DIRECTORY/override" "$WORLD_DIRECTORY/hak" "$WORLD_DIRECTORY/tlk"
cd "$NWN_RUNTIME/bin/linux-x86"
exec ./nwserver-linux -userdirectory "$WORLD_DIRECTORY" -module "$MODULE_NAME" \
  -port "$GAME_PORT" -publicserver 0 -servername "$SERVER_NAME" \
  -servervault 0 -maxclients 8 -dmpassword "$DM_PASSWORD" -interactive
