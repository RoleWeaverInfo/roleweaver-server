# Starting and continuing an NPC conversation — 0.21.0

1. Stand within **3 metres** of an AUTO NPC, right-click it and choose **Talk To** (Speak in some interfaces). You receive a private confirmation; selection itself does not call the AI.
2. Alternatively, address the NPC once within hearing range: `Mira: Hello`, `Mira, can you help?`, or `Hello Mira`. A full name, unambiguous first name or stable ID works. For example, `Dimby, hello` can select Dimby Thornshield, and `Beran, hello` can select Captain Beran.
3. Now speak normally in Talk. You do not need to repeat the NPC’s name. Ordinary follow-up speech works within **6 metres**. Phrases such as “Yes, thank you” and “I agree, but what next?” keep the conversation.
4. With following enabled, your selection remains while you stay within hearing range. While the NPC walks, and for 10 seconds after it stops, ordinary speech also works throughout hearing range. Otherwise move within the ongoing conversation distance to speak; catching up does not require saying the name again.
5. The default timeout is **3 minutes** since your last relevant message or selection. Each new relevant message refreshes it. NPC replies do not extend the timeout.
6. Type `/rw end` to finish, select or address another NPC to switch, or walk outside the retention range. Exact `bye`, `goodbye` or `farewell` also end targeting without an AI reply.

These are defaults. Open **Conversation & Hearing** for your world’s actual game-confirmed values; hearing defaults to 10 metres and can be customized. Initial selection, ordinary follow-up and hearing distances are separate settings.

## Multiplayer behavior

Each player has an independent target. Other players must select or address the NPC themselves; there is no nearest-NPC fallback or automatic group membership. Mentioning a name in the middle of a sentence does not start or switch a conversation. An ambiguous first name never chooses arbitrarily: use the full name, an unambiguous stable ID, or Talk To. Matching nearby player names are considered when resolving an address.

Addressing a recognized other character or using an explicit colon address such as `Kevin: shall we go?` ends or switches the previous target. Unknown comma phrases are treated as ordinary conversation, not guessed to be new names. If talking to someone unrecognized, use `/rw end` or a colon address first. This is deterministic routing, not a general intent classifier.

Changing area, losing required line of sight, reaching the timeout, or an NPC becoming paused, dead or DM-controlled ends the target. With following disabled, leaving the ongoing conversation range also ends it. With following enabled, leaving hearing range ends it. Party chat, tells, DM speech and OOC prefixes `//` and `((` remain excluded. Player nameplates are not disclosed to the AI by this routing.

Multiple players may select the same NPC, but histories remain per player and existing busy/rate limits apply. There is no shared group transcript or simultaneous reply queue.

## Integration and playtest

Install the complete rebuilt bridge and restart once to refresh cached game scripts. The OnConversation wrapper still preserves the original creature handler when AI is unavailable and restores it on unbind. Review custom shops/quests before binding them. No new NWNX plugin or client modification is needed.

Try selecting once, then several ordinary sentences, including “Yes, thank you.” Try a unique first name, duplicate first names, two independent players, walking with an approved moving NPC, catching up after arrival, `/rw end`, and timeout expiry. Check that an unrelated name mention does not switch targets. Dashboard distance changes apply live after game confirmation.
