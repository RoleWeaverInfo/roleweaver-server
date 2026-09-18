# Merchant controls — 0.25.1

## Select a merchant
1. Refresh the dashboard and open **Merchants** in the left sidebar.
2. Choose your NPC from the Merchant list. NPCs appear when their shop permission is enabled in **Controlled Actions**.
3. Wait for **Rules confirmed by game · ready**. The NPC must be connected and have automatic actions and shop permission enabled. Stock cannot be changed during possession, death or combat. Paused merchants can be managed.

## Change haggling
1. Toggle **Allow haggling**.
2. Set **Discount on success (%)**, from 0 to 10. This is taken off the ordinary price.
3. Set **Success chance (%)**, from 0 to 100. For 50%, a game roll of 1–50 succeeds; 51–100 fails. Charisma does not change the chance.
4. Set the time between attempts, from 1 minute to 24 hours. It is also the offer duration. Failed attempts use this time too.
5. Click **Save haggle rules** and wait for game confirmation.

New merchants default to a 5% discount, 50% success chance and ten minutes between attempts. A 100-gold item costs 95 gold after success. Ordinary prices no longer include the old extra 10% markup. NWN rounds discounted prices down to whole gold, minimum 1 for positive-value goods: a 4-gold item with a 10% discount costs 3 gold, so cheap items can have a larger effective percentage reduction. This page does not set custom item prices.

Existing saved rules migrate automatically: the old normal DC becomes its success chance for a character with zero Charisma modifier (DC15 becomes 30%); the normal reduction becomes the discount percentage; the strong-success tier is removed. Check these settings after updating. Existing offers are invalidated.

Saving changed rules invalidates old offers and shop windows. Customers should reopen the shop. Merely saving unchanged rules does not reset attempts. Rules can be saved offline, but only take effect after the game confirms them.

## Add stock
1. Search the catalogue or select an item. The starter catalogue contains15 standard weapons, leather armour, a small shield and healing potions.
2. Enter quantity1–20 and click **Add to store** once.
3. Wait for **Stock saved** and the updated Current stock list.

The game validates blueprints and quantities independently of the dashboard. Up to100 stock rows are supported; stackable items may combine. Custom module blueprints and custom per-item pricing are not part of this version. The module may override a standard blueprint; the live stock list shows the actual item created.

## Remove stock
1. Click **Remove** beside the item.
2. Click **Confirm removal** to remove that entire stock row and its quantity.
3. Wait for **Stock saved**.

If the inventory changed after it was displayed, the edit is rejected; refresh and select again. The game edits a copy, saves it and then switches to that store. An interrupted edit leaves the original stock in place. The dashboard never automatically repeats an uncertain edit. If confirmation times out, check the refreshed inventory before retrying.

Stock edits invalidate existing offers/windows. Existing shoppers must reopen the store. Purchases remain native NWN transactions; the AI cannot use administrative stock commands. Shops retain their inventory over module restarts.

## Backups and testing
Recovery backup format11 includes per-merchant rules; versions1–10 remain supported. Restoring rules creates fresh offer revisions. Actual stock remains in NWN campaign data under your server's userdata/database folder: include that folder in world backups. Role Weaver JSON backups do not restore sold or removed items.

Playtest: change Bram's discount and success chance and save; add one potion; reconnect as a player and ask about stock and haggling; buy the potion; verify gold/stock; remove another test item through the dashboard; reopen the shop to confirm it is absent. With a shop window already open, change rules or stock and verify that customers must reopen it before purchasing.

## Price consistency fix (0.25.1)
NWNX Player is now required alongside the existing plugins. Enable it with NWNX_PLAYER_SKIP=n when using SKIP_ALL. The shop closes and reopens automatically to refresh personal prices. Price questions use final game quotes without applying the discount twice; changed or expired quotes are rejected before speech. After updating, test haggling with a store already open, then verify displayed and charged prices.
