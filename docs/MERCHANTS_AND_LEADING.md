# Leading, home and merchants — 0.25.1

## Lead a player or return home
1. As a DM, record a destination in Controlled Actions, in the same area and within 40 metres of the NPC.
2. Select the NPC and enable automatic approved actions.
3. Check destinations under **Lead a player to** and choose a **Home location**, then save permissions.
4. Resume the NPC in AUTO. As a player, begin a conversation and ask to be led to the named destination. Follow the NPC.
5. Ask the NPC to return home to use its saved home location.

Leading waits when the player falls more than 6 metres behind or loses required line of sight. It resumes when they catch up. It cancels after 30 seconds waiting, beyond 20 metres, or after 120 seconds overall. Walking/home has a 30-second timeout. Combat, pause and DM possession interrupt actions. Players are never moved automatically. Test pathfinding in your module.

## First weapons merchant
1. Open **Controlled Actions** and click **Create Bram, example weapons merchant** once.
2. In NPCs, select **Bram Ironstock**. Log in as a DM, stand where the shopkeeper should be, and use **Spawn at DM**. Choose persistent placement if desired.
3. Resume Bram in AUTO. His example profile already allows opening the shop.
4. Reconnect as a player, select or address Bram, then ask **What weapons do you sell?** or **Show me your wares.** Stay within 6 metres.
5. The native NWN store opens. Buy a weapon, close the store and ask about stock again. Check that the purchased item is absent and your gold and inventory are correct.
6. Restart the module and check that sold items have not returned.

You can instead enable the shop permission on an existing NPC. Every newly created dedicated shop starts with one dagger, shortsword, longsword, quarterstaff and shortbow. Stock is finite; this version has no automatic replenishment or selling items to the merchant.

Conversation uses a fresh snapshot of actual stock and current customer prices. Game scripts validate the customer, distance, control state, item and price; the native game handles payment and item delivery. The AI cannot invent a transaction. Final stock and purchases must be checked in the game client during playtesting.

## Saving and backups
Role Weaver recovery backups include profiles, approved destinations and permissions. **Actual shop inventory is separate NWN campaign data in your server userdata/database directory. Include that directory in your normal world backups.** Restoring a Role Weaver JSON backup does not rewind stock or purchases. Player character saves remain the responsibility of your server; store and character saves are not one crash-atomic transaction.

A missing saved shop is reported as unavailable instead of silently restocking it. Changing or duplicating a profile does not copy its store inventory. These hooks only handle Role Weaver-owned shops, leaving existing module shops alone.

## Haggling
Ask **Could you give me a better price?** during a conversation with an enabled merchant. The AI requests the action; the game rolls `d100()`. A roll at or below the merchant's configured success chance grants the configured discount; a higher roll leaves ordinary prices unchanged. Charisma does not affect the roll. New merchants default to a 50% chance and 5% discount.

Configure both percentages under **Merchants**. Discounts are limited to 0–10%. There are no strong-success tiers or markup reductions. A 30-gold item at 10% off costs 27 gold. NWN rounds down to whole gold, minimum 1 for positive-value goods; cheap items can receive a larger effective discount (4 gold at 10% becomes 3). The extra 10% markup from earlier versions is removed.

The result appears privately in the player's game messages, then the store opens with their prices. The NPC receives those same customer prices on the next chat. The AI cannot choose the roll or discount.

One result per player account and merchant is kept for the configured duration (default ten real minutes), including failures. Repeated requests reuse that result; discounts never stack. Reconnecting, switching characters on that account or restarting the NWN module does not grant another attempt while its Redis record remains. Another account has its own offer. Redis reset/data loss can clear these short-lived records; they are not included in Role Weaver recovery backups.

When an offer expires, an old discounted store window will reject purchases until reopened at current prices. No item or gold is transferred for a rejected purchase. A successful haggle does not guarantee stock remains available.

### Playtest
1. Note the normal price of an item. Ask to haggle and check the private roll message and store price.
2. Buy an item and confirm the gold charged matches the displayed price, and the remaining stock updates.
3. Ask again within ten minutes: the same roll must return with no additional discount.
4. With another player account, check that their prices and roll are independent.
5. After ten minutes, reopen the shop or request a new haggle. Also check an old discounted window refuses purchases after expiry.

## Merchant administration
Use the new Merchants sidebar tab to select shopkeepers, configure haggle rules, and add/remove stock. See MERCHANT_ADMIN.md for step-by-step instructions. The haggling values above are defaults; each merchant can now have their own rules.

## Price consistency fix (0.25.1)
NWNX Player is now required alongside the existing plugins. Enable it with NWNX_PLAYER_SKIP=n when using SKIP_ALL. The shop closes and reopens automatically to refresh personal prices. Price questions use final game quotes without applying the discount twice; changed or expired quotes are rejected before speech. After updating, test haggling with a store already open, then verify displayed and charged prices.
