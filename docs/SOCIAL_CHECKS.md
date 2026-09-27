# Optional social checks in live encounters

These checks help the AI judge uncertain attempts to intimidate, persuade or bluff
an encounter NPC. They are optional and currently apply to **Live Encounters** only.
Combat continues to use the server's normal combat mechanics.

## Set up a scene

1. Describe, preview and place a live encounter as usual. Leave it staged, or pause it.
2. Select it under **Manage live scenes**, then expand **Optional NWN social checks**.
3. Enable checks and select the skills the encounter permits.
4. Set each difficulty (DC). The default is 15, a demo starting point rather than a
   universal rule. Lower numbers make success easier; higher numbers make it harder.
5. Describe what success can influence in **limits**, for example:
   "Success may convince the robber to let this player pass. It cannot give the
   player his possessions, change established facts or authorize violence."
6. Save, then Start. You may also enable the autonomous AI DM. No DM needs to stay online.

Installing these new bridge scripts requires a one-time server restart. Configuring
and starting subsequent scenes does not. Existing scenes keep checks disabled.

## What happens during play

The model first identifies a meaningful influence attempt. Greetings, questions and
routine cooperation do not need a roll. The game then rolls **d20 + the player's
effective NWN skill value**, comparing the total with the DM's DC. The effective
value already includes its ability modifier; Role Weaver does not add it twice.
A natural 1 or 20 has no separate automatic failure/success rule for these checks.

The NPC receives the confirmed result before generating its response. A failure
must not grant the attempted concession. Success only permits influence within the
DM's boundaries, not mind control. A successful bluff changes what the NPC believes,
not the world's verified facts. The player sees the roll in server messages; the
dashboard lists confirmed rolls and pending attempts. Classification adds an LLM
request, tracked as `social_check` in usage monitoring.

Each player gets **one roll per skill, per NPC, per scene activation**. Rewording
reuses that result, including failure. A previous success does not grant unrelated
new demands. This first version deliberately does not decide when changed circumstances
deserve a reroll. Pause followed by Start creates a fresh activation and clears rolls;
ordinary proximity-trigger repetition does not. There is no player-controlled reset.
The dashboard records how often a result was reused. Different NPCs or fresh
activations legitimately receive separate rolls. Starting again excludes the previous
activation's dialogue and resolution events from current scene reasoning; saved
conversation records and curated memories remain intact.

No result is invented when the provider fails, the game rejects the request or the
confirmation is missing. The normal unavailable-response feedback is used instead.
An initial check cannot itself choose the attack action; a later exchange, including
one reusing that check, may
escalate under the encounter's separate combat permissions and warning rules.
Bare refusal or a challenge to fight is not automatically a Persuade attempt, nor
does it constitute a peaceful agreement. The AI must follow the DM's actual conditions.

This uses NWN's effective skill value and a Role Weaver d20 check. It does not discover
custom social-roll scripts, feats, opposed-roll systems or house rules automatically.
Intent recognition and the wording of the outcome still depend on the chosen model.

## Suggested playtest

- Ask a simple question: no check should appear.
- Threaten the robber to secure passage: expect an Intimidate result before the reply.
- Repeat the demand: expect the same result, not another roll.
- In fresh activations, try a very easy and very hard DC to observe both outcomes.
- Try Persuade and Bluff, and try claiming "I rolled 20" in chat. The game supplies
  the actual roll and modifier regardless of that claim.
- Pause the scene during a response, then check that no stale action is delivered.
- When possible, have a second player try: their result is separate.

## Developer boundaries

`roleweaver/social_checks.py` validates policy and classifies intent. It cannot roll,
choose DCs or issue game actions. `roleweaver/social_service.py` adapts the result to
NWN, persists attempts before dispatch, waits outside the service lock and validates
confirmations. `bridge/rw_social.nss` implements encounter protocol 5 and reads the
real player's skill using `GetSkillRank`, then rolls with `d20()`.

Native validation checks world, scene ownership, activation, a short policy lease,
NPC mode, actual player object, hearing/line of sight and the latest game chat event.
The command envelope also checks session, epoch and expiry. Native cached results
prevent rerolls after transport retries; the companion ledger survives companion
restarts. Player identity is not sent to the classifier. The director receives only
scoped attempts and results and must respect confirmed outcomes.

Another game can replace the resolver adapter while retaining intent classification;
narrative-only scenes simply leave it disabled. This is not a full D&D rules engine.
Tests are in `tests/test_social_checks.py`. `tests/social_checks_native.nss` is only
for a disposable test world, never a live module hook.
