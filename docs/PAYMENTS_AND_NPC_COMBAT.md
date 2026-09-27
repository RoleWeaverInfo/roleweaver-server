# Payments and NPC-to-NPC combat

Both capabilities are off by default and configured per NPC under **Controlled Actions**.

## Request payment through the existing exchange window

Enable controlled actions and **Request payment**, enter a purpose, starting amount and lowest negotiated amount. The model chooses from five bounded amounts (fewer if amounts overlap). The recipient is the requesting NPC. Keep the player within 3 metres, visible and out of combat.

A request opens the existing Role Weaver exchange window with the exact recipient and amount and a **Confirm payment** button. Item gifts and barter retain their existing permissions and separate confirmation. Selecting items never pays gold, and paying gold never transfers selected items. Payment-only NPCs do not gain item-transfer permissions.

Closing the window pays nothing. Offers expire after 120 seconds; a replacement offer invalidates the old button. Pausing the NPC, changing permissions, moving away, combat or a respawn invalidates confirmation. The game checks the balance and transfers gold only on explicit confirmation. It exports the player character after success. Insufficient funds take nothing.

The companion records confirmed receipts and supplies them to the NPC and the encounter AI DM. A spoken claim, an offer, or a model response cannot establish payment. Receipts are observations, never instructions to replay transfers after a restart. World save scripts still govern durable game gold; this does not promise an atomic save across the module, character file and companion database. Item-and-gold barter, rewards and automatic captive release are separate capabilities.

## Optional combat between AI NPCs

Enable **Initiate combat against other AI NPCs** on the attacker, describe the conditions and select permitted targets (or any eligible AI NPC). Enable **Allow this NPC to be targeted** on each intended target. Both need controlled actions and AUTO mode.

Targets must be visible, alive, within the configured radius, and neither players nor DM-possessed. An encounter actor cannot attack an NPC reserved by another encounter. The AI DM may select currently approved attacks while monitoring a scene, including a threat against an opted-in captive. Ordinary AI NPC dialogue can also select permitted attacks. Natural-language conditions guide the model; they are not a substitute for the hard target, distance and permission limits enforced in code.

Game scripts execute the combat. Pursuit distance and withdrawal health apply. Revoking permission or losing the companion permission lease causes an ordered withdrawal. Native combat, factions, plot flags and server scripts still affect the result. These permissions do not provide a protect or escort action, or expand authorization to attack players.

## Playtest

1. Request payment of 100 gold and close the exchange: no gold should move.
2. Request again and confirm: the player loses 100 gold, and the NPC gains it. The next response should recognize the confirmed payment.
3. Test insufficient funds, waiting over 120 seconds, moving away and changing the amount before accepting an older offer. No stale payment should succeed.
4. Verify ordinary item gifts/barter still work independently.
5. Opt in two test NPCs and request an approved attack. Remove target permission and check withdrawal. Repeat with target permission off: no attack choice should be available.
