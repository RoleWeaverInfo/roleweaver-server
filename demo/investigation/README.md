# The Missing Royal Caravan

A conversation-led investigation for the Crown Hall in YourWorld_Fixed.mod. The innkeeper and merchant keep their existing profiles, memories, placements and stock. Captain Beran, Aldren, Meriel and Holt live in the hall; the King arrives for an audience.

## Play

1. Approach Beran, select Talk To, and discuss helping the Crown. He can appoint you Royal Investigator and suggest where to begin.
2. Question witnesses naturally about the caravan. Role Weaver reveals their own accounts in character. A private journal notification confirms each recorded account; `/case` shows your notes.
3. Question Holt and compare his story with the witnesses. He can lie according to his authored cover story.
4. Ask Beran to arrange an audience. Approach the King and select Talk To or say `King: Hello`.
5. Explain who you accuse and what two witnesses told you. You can use several messages and paraphrase the evidence. The King asks follow-up questions if the case is incomplete. There are no native conversation menus or required evidence keywords.
6. A supported accusation can earn 100 gold once per visit. The game announces actual completion and payment.

The configured LLM must be online for the story. Provider failure or blocked speech grants no progress. Investigation appointment, clues and completion restart on each login. NPC conversations and personal memories persist. The model sees the recent 16-message conversation with this NPC, with earlier visits labelled as personal memory rather than current evidence; for a long discussion, briefly recap your case.

## How it works

`rq_chat` preserves `/case` but sends spoken investigation dialogue through the ordinary Role Weaver chat, privacy and safeguard path. `rq_load` explicitly enables two optional module-owned bridge hooks. Worlds that do not enable them behave as before.

`rq_context` supplies player-specific story state and a bounded list of allowed proposals. A witness may record only their own account; the King receives only this player's collected accounts. The LLM interprets narrative meaning and returns ordinary speech plus at most one proposal. The companion accepts only an offered proposal. Output safeguards can cancel it.

After successful native speech delivery, `rq_reply` rechecks the listener, range, line of sight, AUTO mode, possession, current request token, appointment, recorded evidence and completion flag. It consumes the token once. It never executes a player-provided script name. Audience creation retains the duplicate and stale-lock protections. The King stays seated while speaking; no conversation action needs to interrupt him.

Meaning is judged by an LLM, so false interpretations remain possible. Native checks prevent invented evidence bits, uncollected accounts and repeat payments; they cannot prove that a generated sentence accurately expressed an account or that an accusation was semantically correct. Compare providers and report misjudgments. Old assistant suggestions are explicitly excluded as player testimony in the prompt.

## Data and recovery

Investigation flags live on the player's current game object. `rq_enter` resets them on login and `rq_exit` invalidates them on departure; both preserve any existing world event handler. The reset affects only that player, not other investigators or the shared King. Restarting the module also starts fresh investigations. The demo permits a new 100-gold reward each visit; it does not remove gold already held by the character. This replay policy is for the small demo, not a recommended economy policy for a persistent world.

NPC conversations and curated memories remain in the companion database. A visit marker labels earlier conversation as personal memory, so introductions remain usable without treating old testimony as this visit's evidence. Back up companion data and the game's native shop database as usual. Legacy `rq_caravan_*.sqlite3` files are no longer used for progress; there is no need to delete them or clear conversations to replay the demo.

## Edit and install

- `content.json` and `lore/`: authored characters and knowledge. Keep these copies aligned.
- `scripts/rq_context.nss`: story state, available proposals and interpretation guidance.
- `scripts/rq_reply.nss`: authoritative progress, audience and reward checks.
- `scripts/rq_inc.nss`: shared journal and audience helpers.
- `noticeboard.txt` and `rq_board.nss`: Examine and Use instructions.
- `build.py`: first installation into the original Crown Hall module.
- `update.py`: update an existing investigation while preserving unrelated resources; removes the retired court menus.

Compile the demo entry scripts and updated `rw_modulechat` and `rw_tick` using the matching game runtime, NWNX headers and your world's `rw_settings`. Install the matching companion Python code (`story.py`, `provider.py`, `service.py`, `services/dialogue.py`). Old bridge binaries do not carry story context. Review module and override precedence, back up, and restart the game and companion together. Do not rerun `seed.py` merely to update scripts: seeding intentionally restores demo-owned authoring content.

## Tests

Run `python -m unittest discover -s tests` and `python demo/investigation/test_content.py` from the repository root. `tests/native_story_checks.nss` exercises evidence-mask rejection, hook registration, audience spawning and non-player rejection on an isolated NWNX server.

Playtest with the configured provider: collect clues through paraphrased questions; discuss unrelated shopping without recording clues; try a wrong suspect, a single account, a denied accusation and an instruction to invent evidence; present a valid case over multiple messages; repeat it after completion; test two players, pause/possession and a provider failure. No menus should open. End-to-end semantic quality requires this human playtest.

## Expanded setting and editing

The demo includes six public lore documents and seven individual backgrounds,
with personal tastes, work, home life, ambitions and relationships. Private
investigation facts remain scoped to each witness. See [EDITING_GUIDE.md](EDITING_GUIDE.md)
before moving objects or refreshing content after editing. `refresh_content.py`
updates authored lore and voices without resetting placements or game settings;
player-history clearing is a separate opt-in switch.
