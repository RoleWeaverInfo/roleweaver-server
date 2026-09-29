# World text translation (development preview)

Players can read supported object text, public NPC and player character descriptions,
NPC/placeable hover labels and prepared standard NPC dialogues in their preferred language. The native
Examine window remains unchanged. A private reading window opens alongside it when
a cached translation is available. Nothing is written back to shared object text.

Included in the prepared Alpha 0.3.0 packages; absent from Alpha 0.2.0.

## Administrator setup

For guided path selection and preparation, run **`bash setup.sh`**. Option **1**
prepares the bridge import, **7** prepares existing standard dialogues, and **8**
builds the optional native adapter with path-specific installation instructions.
See [Guided setup](GUIDED_SETUP.md). These tools prepare files; they do not change
a running server or trigger LLM requests.

1. Install the updated companion **and** bridge scripts. The bridge needs NWNX
   Events, Player, Dialog and Util, plus NWN:EE NUI support. For an existing installation, rebuild its bridge
   using the normal add-on procedure and restart NWN once to load the scripts.
   Keep your module's existing event handlers; `rw_init` subscribes to the Examine
   and disconnect events, so no new module event slot is required. To use the optional
   dialogue test, copy `assets/rw_tr_demo.dlg` into the server's `override` folder
   alongside the compiled bridge scripts. Prepared add-on bundles include it in
   `optional-assets/`; demo module builds include it in `compiled/`.
2. Configure an online provider or LM Studio in **LLM Settings**.
3. Open **World administration → Translations**. Enable the service, choose the
   source language and languages to offer players, then save. Translation is off
   by default. It uses the active provider/model, or the optional model override
   from that same provider. The default limit is six text jobs per minute; a name
   and a description count as separate jobs. Provider fallbacks can make more than
   one HTTP request per job; this setting is not a spending cap.
4. Supported world objects are now included automatically. **There is no need to
   mark ordinary placeables, doors, identified items or public character descriptions.**
   Exclude any objects whose text should stay untranslated, such as an editable
   book or sign that your server's policy excludes.
   See the controls below.

## DM exclusions

Stand within ten metres of an object and type in Talk:

```text
!rw translate rq_testchest off
```

Replace `rq_testchest` with the object's Toolset **tag**, not its display name.
The nearest matching object is used. `off` excludes it, including when a
translation is already cached. `on` removes the exclusion:

```text
!rw translate rq_testchest on
```

These commands affect the running object until it or the server resets. To make
an exclusion permanent, add the **integer** variable `rw_no_translate`, value `1`,
to that object or its blueprint in Aurora. An object creation script can also use:

```c
SetLocalInt(oObject, "rw_no_translate", TRUE);
```

Public descriptions are eligible regardless of who wrote them. Player chat, tells
and logs remain excluded; a biography shown through Examine is a separate reading
surface. Role Weaver does not infer authorship from a description. If your world
excludes a particular editable object, set the flag in its creation/edit handler
or blueprint. For an object that players may
already be examining, the bridge helper also closes its existing private reading
windows and invalidates pending replies:

```c
#include "rw_translate"
// Inside your server's handler, when excluding this object's text:
RWTrSetExcluded(oObject, TRUE);
```

The earlier preview's `rw_translate=1` opt-in flag is no longer required or read.
To migrate an earlier explicit exclusion, use `rw_no_translate=1`; an absent or
zero old opt-in flag no longer prevents translation.

## Player instructions

1. Type `/rw language` in **Talk**. This opens a private menu and hides the command
   from chat and NPC conversation processing.
2. Select a language, then turn translation **ON**. The preference is saved for
   that player's public-key identity and applies to their characters on this world.
3. Examine a supported object, NPC or player character. The first time, only its normal original-language
   Examine window may appear. Close it and examine again after the translation is
   ready. Both windows can be closed normally; **Show original text** in the
   reading window switches to the source. The same button then becomes **Show
   translated text**, allowing repeated comparison without more LLM requests.
4. Use `/rw language` again to turn translation off or change languages. Players
   never need access to the dashboard.

The preview offers English, French, Spanish, German, Italian and Portuguese.
Selecting the source language uses the original text without an LLM request.
Font coverage and accented text should be included in client playtesting.

### Public NPC and player descriptions

Both **ordinary NPCs and Role Weaver AI NPCs** are included automatically. The
translation uses the name and public description shown in Examine. It does not
expose the AI profile's personality, secrets, memories or restricted lore. An NPC
with no public description can still have its descriptive name translated, but
Role Weaver does not invent a biography from its private AI profile. Give it a
public Description in Aurora if you want visitors to read one.

The character description/biography that another player can read through normal
**Examine** is translated on demand by default. It uses the same private reading
window and original/translation toggle. A character's **name is always preserved**,
even if its name policy is set to Translate. No account details, character file
names, private AI profiles, chat history or private server records are read for
translation. Only the public description is sent to the translation provider.

Public NPC and player biographies up to **8,000 UTF-8 bytes** are accepted (8,000 plain ASCII
characters; fewer for accented or other multibyte characters). Each biography is
one translation job, with a larger response budget when needed. Empty or oversized
descriptions remain original. Changing the description requests a new translation
on its next examination; unchanged descriptions reuse the cache across viewers
and logins. A rename alone does not translate the biography again. Existing open
windows are not refreshed automatically: close and reopen after an edit.

NPC names use the Auto / Preserve / Translate policies below. This covers the
game's public description, including updates made by a server's
description editor. Custom profile windows or records that are not exposed by
normal Examine still need their own integration. DM avatars and DM-possessed
creatures are not treated as player biographies. The `rw_no_translate` exclusion
also applies to player characters when set by a server script.

## Hover names and proper names

NWNX Player provides private name overrides for **creatures and placeables**.
When translation is on, visible objects in the player's current area are checked
in small batches every five seconds (up to 128 nearby objects). The game does not
send a general mouse-hover event, so this bounded visibility scan prepares names
for their normal mouse-over labels. It does not request their descriptions or
scan other areas. Players and DM-possessed creatures are
excluded. Shared names stay unchanged; two players may see different translations.
Doors and item hover labels cannot use these APIs and retain their original names;
their names can still be translated in the private Examine reading window.

No click or Examine is needed for supported hover names. The first label may be
original until its job completes, then a later scan applies the cached translation.
At six new jobs per minute, a room with many different names may take several
minutes to fill the cache. Already cached names use no additional model requests.
Turn translation off to restore original labels. If no mouse-over labels appear
at all, check that mouse-over feedback is enabled in the NWN client's settings.

The bridge accepts NWN's native **unpadded hexadecimal object IDs** (for example,
`3` and `e`), as well as padded IDs. Earlier preview builds incorrectly required
eight digits, rejecting hover requests before they could reach the cache.

Automatic name translation asks the model to preserve personal/place names and
translate descriptive roles and titles: for example, translate “Captain” in
“Captain Beran” but preserve “Beran”. This is a model instruction, not a guaranteed
proper-name classifier. The DM can override it using the object's Toolset tag:

```text
!rw name TAG preserve
!rw name TAG translate
!rw name TAG auto
```

Stand within ten metres of the target. **Preserve** keeps the entire name as written;
**translate** classifies it as a descriptive label; **auto** uses the mixed-name rule.
These commands last until the object resets. For permanent settings, set integer
`rw_tr_name_mode` in Aurora: `0` = auto, `1` = preserve, `2` = translate.
`rw_no_translate=1` takes precedence over all three policies. Player character
names always remain unchanged, regardless of policy.

Changed source names and policies clear old overrides at the next scan. Turning
translation off, changing language, leaving the area or disconnecting clears the
player's overrides. A translated NPC label can also be used as a direct address
(`Translated label: Hello`); normal names, stable IDs and Speak selection still work.

## Try a standard NPC dialogue

This is an **optional authored test conversation**, separate from AI-generated
free-form conversation. It now uses the same on-demand hooks as the general
preparation tool below. It does not change other NPCs' assigned dialogues.

1. In the updated test module, find the **Royal Guide** just inside the hall entrance
   on your right. Right-click **Speak** (or click the NPC normally). This is an
   ordinary module NPC with `rw_tr_demo` assigned as its Conversation, not an AI NPC.
   No chat command or AI profile is needed.
2. The native NWN dialogue asks: “Welcome to the Kingdom of Role Weaver. What would
   you like to know?” Choose where to buy supplies, who knows the kingdom, how to
   explore the demo, or goodbye. Each information branch offers another question
   or goodbye. There are no purchases, rewards or quest changes in this fixture.
3. With translation off, all lines and choices are English. With translation on,
   missing lines appear in English while jobs are queued. Close the dialogue and
   speak to the Royal Guide again later to use cached translations. Already open dialogue
   tokens are not rewritten underneath a player.
4. The opening page requests its greeting and four available replies. The three
   information branches and their return option are requested only when reached.
   At the default six jobs per minute, an object/name backlog can delay these jobs.
   Inspect progress or adjust the rate on the Translations page. Reopening cached
   choices does not issue another provider request.

The Royal Guide has no AI behavior to pause or resume. The developer command
`/rw dialogue` remains available at a selected AI NPC; that path pauses its AI
activity and restores its previous mode afterward, respecting later DM changes.
Busy, fighting, possessed, DM-controlled or excluded NPCs are unavailable.
Translation failures fall back to English; they never choose a branch or execute an action.

Builders can edit `examples/translation_dialogue.json`, then run:

```bash
.venv/bin/python tools/build_translation_demo.py
```

This regenerates `assets/rw_tr_demo.dlg`, `assets/rw_tr_guide.utc`,
`bridge/rw_tr_demo.nss` and the generated `bridge/rtd_*.nss` condition wrappers;
rebuild the bridge and install them together. The guide uses `rw_tr_talk` to begin
the native conversation. Each reached condition fills its own private token from
the cache. English remains in the DLG Text field and comment.
This fixture reserves **per-player custom tokens 2000000–2000008**. If your world already
uses them, change `token_base` in the JSON before generating and compiling. The
translation provider receives text only: branch links and token IDs are authored
locally and are never supplied by the LLM.

To add the guide and dialogue to a **new copy** of an existing module:

```bash
.venv/bin/python tools/add_translation_guide.py --module /path/to/YourWorld.mod --output /path/to/YourWorld_WithGuide.mod
```

The source module stays unchanged. The builder adds one guide near the entrance,
preserving other creatures, placeables and module hooks. Move the guide in Aurora if
needed. Install the updated compiled bridge scripts, including `rw_tr_talk.ncs` and
`rw_tr_end.ncs`, with the resulting module. This helper adds only test content; it
does not install or activate Role Weaver on an unintegrated server.

## Prepare your world's existing dialogues

This is an **offline setup step**, not a background translation sweep. Role Weaver
reads local DLG resources to create wrappers and a review manifest. It makes **zero
LLM requests** and writes **nothing to `translations.sqlite3`** during preparation.
There is no automatic discovery/categorization of every NPC in the running world.

Run from the extracted Role Weaver package or source checkout. Your module stays
where your NWN server already loads it; it is read, never moved or modified.

1. Build the current bridge with your normal world settings. Keep its source folder
   (including `rw_settings.nss`, `rw_tr_nodes.nss` and other bridge includes).
2. Enable `NWNX_DIALOG_SKIP=n` and `NWNX_UTIL_SKIP=n` in your server launcher, alongside
   the existing Player, Events and other Role Weaver plugins. Keep matching `.so`
   binaries and `.nss` headers. Missing Util prevents wrapped conditions from passing;
   do not install a prepared bundle without it.
3. Prepare a new bundle. This example assumes your existing world at `~/nwn-world`,
   runtime at `~/nwserver`, headers at `~/nwnx/nwscripts`, compiler at `~/bin/nwnsc`,
   and the bridge source in `builds/my_world-bridge-01/scripts`:

   ```bash
   .venv/bin/python tools/prepare_dialogues.py --module "$HOME/nwn-world/modules/YourWorld_Fixed.mod" --output builds/my_world-dialogues-01 --compiler "$HOME/bin/nwnsc" --runtime "$HOME/nwserver" --includes "$HOME/nwnx/nwscripts;$PWD/builds/my_world-bridge-01/scripts"
   ```

   Change those paths to match your installation. Add `--resources /path/to/extracted-dialogues`
   for loose override or extracted HAK resources; later resource folders take precedence
   over the module. HAK archives are not automatically unpacked. Choose the effective
   resources your server actually uses. Add `--dialogue resource_name` to start with
   one conversation. Omit the compiler/runtime/includes options for a source-only bundle.
4. Read the generated `INSTALL.md` and `manifest.json`. They list original condition
   scripts, generated wrappers and the custom-token range. General bundles default
   to **3000000 onward**, separate from the Royal Guide. Use `--token-base` for another
   range if necessary. Literal token conflicts in supplied sources are detected;
   tokens calculated by scripts or used in resources you did not supply require review.
   Existing prepared dialogues are listed as skipped, never wrapped twice.
5. Stop NWN for installation. Back up same-named files already in the server's
   `override` folder. Copy the **contents of the new bundle's `override/`** into it.
   For source-only bundles, compile `scripts/rtd_*.nss` first and copy those `.ncs`
   files too. Keep all original condition and action scripts available. Start NWN.
6. Test the NPC first with translation off, including restricted choices, quest
   updates and rewards. Turn translation on using `/rw language`, then repeat.

The graph, links, action scripts/parameters, condition parameters, quests, delays,
animations, sounds and authored/localized text stay intact in the prepared file.
Generated conditions execute the original compiled condition once per engine
evaluation, preserving its return value. Only successful conditions reach the
translation hook. Actions still run under the game engine; the LLM cannot choose
an answer, grant a reward or advance a quest.

At runtime the hook reads the reached native text (including text resolved from
the server's talk table). It requests only that line or available reply. A cache
miss leaves the normal text visible. A bounded, three-minute background subscription
can deliver the completed result for the next visit without opening windows or
rewriting current choices. Reopening later retries an expired subscription. The
game keeps up to 64 recent nodes per player; SQLite supplies durable shared reuse.

Editing dialogue text or choices in Aurora: edit the **original** module/resources,
then regenerate and install a new bundle during maintenance. The newly reached text
is hashed again; only changed text needs another translation. The original module
remains your authoring copy. Do not edit the generated wrapper scripts or reuse an
old prepared override after updating its original dialogue. A cache correction is
refreshed asynchronously on the next visit and used when that node opens again.

Multiplayer dialogue: the optional [NWNX_RWTranslation adapter](../extensions/nwnx_translation/README.md)
substitutes a private copy of each outgoing entry, reply list and chosen reply for
each actual viewer. It does not change who can see the conversation. Different
viewers can use different languages, including translation off. A missing cached
translation leaves that viewer's original text visible until a later visit.
No shared dialogue text, reply IDs, conditions or actions are changed by the adapter.
Only text the engine is already sending is requested; nearby players who are not
viewers do not cause translation jobs. NPC speech/chat outside the dialogue panel
remains original. The adapter currently targets Linux NWN/NWNX **8193.37-17**;
build against matching headers and Core. It requires one maintenance restart.

Without the adapter, the compatibility path still requires the speaking player
to be the **only connected player in that area** for native replacement; otherwise
it leaves the original visible. Examine and hover-name overrides have no such
area restriction. Installing the adapter requires recompiling existing prepared
`rtd_*.nss` wrappers against the updated bridge, but not regenerating their dialogue
graphs. See the adapter guide for installation and rollback.

Preview limits: custom conversation systems need separate integration. Text containing dynamic/custom tokens or markup
(`'<...'`) is deliberately left native and is not sent to the provider; this prevents
resolving player names or player-authored token values into translation requests.
Empty or over-2,000-character nodes also stay native. No automatic translation of
NUI/custom menus, chat, tells or logs is added by this tool.

Rollback: stop NWN, remove only the generated files listed by this bundle and restore
the original override files you backed up. Restart NWN. Do not delete your original
condition scripts, module, HAKs, player data or translation database.

## What is included

- Placeables, doors and **identified** items by default, with explicit DM exclusions.
- Object names and descriptions up to 2,000 characters, plus public NPC and player
  biographies up to 8,000 UTF-8 bytes. Longer text retains its original display.
- Shared cache reuse across players and game/companion restarts.
- Independent name/description hashes: changing a name does not retranslate an
  unchanged description. Changes are discovered on the next examination.
- Checks against the current player, world session, object, preference request and
  source text before a cached reply opens a window. A delayed old reply cannot
  replace a newer examination.
- Administrator cache inspection, manual corrections and retranslation on the
  next examination. Corrections win over an older request still in flight.
- Separate worker, bounded queue, provider timeout and retry delay. Failed
  translations leave the original available. Usage & Performance records the
  `translation` request phase.

Chat, tells, combat messages, logs, private profiles, AI NPC profiles, unprepared
NPC dialogues and client/custom menus are **not translated** by this milestone.
Public player descriptions shown through Examine are included, even when written
by the player. Servers can exclude individual objects as described above.
This does not intercept every text string sent by the game.

## Cache and recovery

`data/translations.sqlite3` contains cached source/translated text, administrator
settings and hashed player preferences. Source hashes include language, text
kind, full text, resource context and a cache schema revision. API keys are not
stored in this database. Translation content never becomes NPC lore or memory.

The managed dashboard now includes this database in coordinated recovery ZIPs,
alongside world memories, usage and the player identity salt. Open **Database &
Recovery** for automatic backup settings, integrity checks and full or
translation-only restore. Follow [Database recovery](DATABASE_RECOVERY.md).
Existing `translation-backups/*.sqlite3` files remain untouched for manual recovery;
the managed dashboard no longer runs that separate five-file backup schedule.

**Translations → Translation diagnostics** shows worker state, active request time,
queued jobs, rate-limit waiting, cache counts by language, cache hits, recent
provider errors and last-hour requests/tokens/estimated costs. Prices must be set
under **Usage & Performance**; missing prices remain unknown. Fallback attempts
can generate multiple HTTP calls per job. Select **World text translation** in
Usage & Performance to inspect this request category separately.

Diagnostics refresh without replacing unsaved settings or cache corrections.
**Download diagnostics** exports technical settings and counts without cached text,
player IDs, model names, endpoints or credentials. Error advice uses exception
categories and HTTP codes; raw provider messages are excluded. Native plugin
readiness comes from the current bridge heartbeat. An old or disconnected bridge
cannot confirm it, and the panel cannot verify every module hook or dialogue.
Exclusions/unsupported text rejected inside the game never reach this database,
so their frequency cannot be inferred from these counts.

Disabling the service prevents new jobs from starting. A request already sent to
a provider can finish; cached text remains available for later re-enabling. Game
preferences refresh within about 15 seconds. Text already on screen is not
continuously rewritten when a builder edits the object; close and reopen Examine.

## Suggested playtest

The developer's two-client playtest passed with German and Spanish viewers on an
English server: each saw the correct private dialogue translation, while public
spoken dialogue stayed in English. This verifies that scenario, not every custom
dialogue/HAK combination. Repeat the checks below on each target world's scripts.

1. Enable translation. Use the demonstration chest or a noticeboard without adding any object flags.
2. Choose French in game and turn translation on. Examine, wait and reopen.
3. Check accents, paragraphs, numbers and original-text comparison. Reopen again
   and confirm the cache hit count increases without another translation job.
4. Try a second player in another language. Their window must be independent.
5. Rename the object or change its description. Reopen: the old translation must
   not appear for the changed field. The other field should remain cached.
6. Switch to another object quickly, turn translation off, then log out and back
   in. Old replies must not reopen the previous object; the preference persists.
7. As DM, exclude the chest with `!rw translate rq_testchest off`. Reopen it: no
   translation window should appear, even if cached. Use `on` and reopen to restore it.
8. Try normal chat, tells, an excluded object and an unidentified item. None should
   create translation cache entries. Restore service/model connectivity after a
   failure and reopen after the retry delay to test recovery.
9. Speak to the Royal Guide. Try all three branches, return and goodbye in English,
   then with translation on. A second player with translation off must still see English.
   For the optional `/rw dialogue` test on an AI NPC, closing it should restore that
   NPC's prior AI mode.
10. Check a role label such as Merchant and a named NPC such as Captain Beran.
    Try the three DM name policies, change languages and turn translation off.
    Player names must never change. Address an NPC using its translated hover label.
11. Examine an ordinary NPC, an AI NPC and a player with public biographies. Wait
    and reopen to read their translations;
    toggle back and forth and check the character name remains exactly as written.
    Edit the biography through your server's usual controls, then re-examine: only
    the new text should need translation. Also test a biography longer than 2,000
    characters and two viewers using different languages.
12. With translation on, hover over the noticeboard, supply chest and an NPC with
    a role label such as Merchant. Wait for new jobs to finish; their labels should
    update without opening Examine. Verify original labels return when translation
    is off and that another viewer can retain a different language. A personal
    name may correctly stay unchanged. Doors and item hover labels are not covered.
13. With the native adapter installed, use two clients in the same area. Let one
    start a normal conversation and the other observe using the module's normal
    conversation visibility. Choose different translation languages, then turn
    one off and swap the initiating player. Revisit cached lines. Each actual
    viewer should retain their own language; another nearby non-viewer should not
    get a window or a translation request. Check available/unavailable choices,
    quest conditions, goodbye and rewards. Test public and private dialogues.

Automated tests: `python -m unittest tests.test_translation tests.test_translation_surfaces tests.test_prepare_dialogues`.
`tests/dialogue_preparation_native.py` and `.nss` compare original and prepared
dialogue conditions in an isolated NWN server, including parameter forwarding and
unavailable branches. They are test fixtures, not live-world content.
`tests/run_dialogue_native.py` also runs the adapter's test-only hooks against
real engine string types with simulated recipients, including active/inactive
replies, nested contexts and unchanged originals. It does not replace the two-client
playtest above. Never install a test build of the adapter in a live world.
`tests/translation_native.nss` is a separate isolated-server fixture, not a module
load handler to install in a live world. Actual player-window layout and language
rendering still require an NWN client playtest.
