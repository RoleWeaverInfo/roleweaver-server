# Per-viewer NPC dialogue translation

`NWNX_RWTranslation.so` is an optional Role Weaver NWNX plugin. It replaces only
the outgoing text copy for each actual recipient of a standard NPC conversation.
It does not decide who can view a dialogue, choose replies, rerun conditions,
execute quests, change shared NPC text or translate chat/logs.

This development preview targets **Linux x86-64 NWN/NWNX 8193.37-17**. Build it
against the same unified headers and `NWNX_Core.so` used by that server. Other
engine builds require compatibility work and native tests before use. This is a
Role Weaver extension, not an upstream NWNX plugin or a client modification.

## Build and install

The example uses `~/unified` for the matching NWNX source checkout and
`~/nwnx/plugins` for installed plugins. Adjust those two paths to your installation.
Run from the Role Weaver source directory on Linux:

```bash
sudo apt install build-essential cmake
cmake -S extensions/nwnx_translation -B builds/translation-adapter \
  -DNWNX_SOURCE="$HOME/unified" \
  -DNWNX_CORE="$HOME/nwnx/plugins/NWNX_Core.so" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build builds/translation-adapter -j2
```

1. Prepare the updated bridge with your usual world-specific settings. Its compiled
   scripts must include `rw_tr_send.ncs`. **Recompile existing `rtd_*.nss` dialogue
   wrappers** with these updated bridge includes; the wrapper source and prepared
   `.dlg` graph do not need regeneration for this adapter upgrade.
2. Stop the game server for maintenance. Back up its current bridge scripts,
   prepared dialogue wrappers, launcher and any existing adapter plugin.
3. Install the updated compiled bridge and wrappers in your server's `override`
   directory. Copy the production plugin:

   ```bash
   cp builds/translation-adapter/NWNX_RWTranslation.so "$HOME/nwnx/plugins/"
   ```

4. Add this to your game-server launcher before it starts NWN, keeping your existing
   NWNX plugin path and preload settings:

   ```bash
   export NWNX_RWTRANSLATION_SKIP=n
   ```

   NWNX Dialog, Util and Player must also remain enabled. Start NWN and confirm
   `NWNX_RWTranslation` loads successfully. Missing/incompatible adapters retain
   the older same-area fallback; they do not enable multiplayer translation.
5. Enable the companion's translation service and choose `/rw language` in Talk.
   Test with two clients who can normally view the same conversation: different
   languages, one off, swapping initiator, public/private dialogue, quest choices
   and rewards. First encounters with uncached text retain the original; reopen
   after translation. A nearby non-viewer must not receive a window or request.

The plugin makes no network/LLM calls and needs no provider keys. `rw_tr_send`
reads the recipient's game-side cache and queues ordinary asynchronous Role
Weaver translation requests. SQLite still shares results across viewers of the
same language. Provider latency never blocks the engine's outgoing dialogue.

Rollback: stop NWN, restore the backed-up bridge/wrappers and launcher, restore or
remove just this adapter `.so`, then restart. Do not remove player data, modules,
HAKs or the translation database. See [translation instructions](../../docs/TRANSLATION.md)
for exclusions, offline dialogue preparation and cache management.

## Developer design

Generated condition wrappers register a node only after the original condition
passes. Registration validates the source against the active dialogue. The adapter
scopes that metadata to the current conversation, then hooks the engine's outgoing
entry, replies and chosen-reply messages. It changes a copy for each actual
recipient and passes all other arguments through unchanged. Both active and
inactive reply entries remain in the outgoing array with their original IDs.

Missing context, ambiguous source associations, oversized arrays, dynamic markup,
unknown recipients, exclusions and missing translations retain native text. The
registry is bounded and removed on dialogue cleanup; stack scopes isolate nested
conversations. Only standard dialogue panel messages are hooked. Public floating
speech and other chat messages are deliberately unchanged.

`TranslationTests.inc` is compiled only with `-DRW_TRANSLATION_TESTS=ON` in a
**separate test build**. Never install that binary on a live server. With a prepared
demo module and compiled bridge in a staging directory, run:

```bash
cmake -S extensions/nwnx_translation -B builds/translation-adapter-tests \
  -DNWNX_SOURCE="$HOME/unified" \
  -DNWNX_CORE="$HOME/nwnx/plugins/NWNX_Core.so" \
  -DRW_TRANSLATION_TESTS=ON
cmake --build builds/translation-adapter-tests -j2
python3 tests/run_dialogue_native.py \
  --module /path/to/staging/YourWorld_Fixed.mod \
  --scripts /path/to/staging/compiled \
  --runtime "$HOME/nwserver" --nwnx "$HOME/nwnx" \
  --compiler "$HOME/bin/nwnsc" \
  --plugin builds/translation-adapter-tests/NWNX_RWTranslation.so
```

The runner creates a temporary user directory and a non-public server on port
5199, cleans up its process, and keeps its logs for inspection. It tests real engine
string types and hooks with simulated recipients, plus actual dialogue conditions
and action execution. It never changes the live module. It does not verify real
network clients' rendering; the two-client playtest remains required.
