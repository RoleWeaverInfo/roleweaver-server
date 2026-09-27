# Inventory, exchange and assistance

These features use actual NWN objects. The model chooses a finite action ID;
NWScript validates the target, ownership and permissions again before moving
anything. Personal inventory is separate from a merchant's store inventory.

## Enable on a test NPC

1. Install the updated bridge scripts, including `rw_inventory.nss` and
   `rw_trade_evt.nss`, and restart the module once. Subsequent permission changes
   need no restart. Use the normal add-on builder to include all dependencies.
2. Enable the **NWNX_Item** plugin. If the launcher uses `NWNX_CORE_SKIP_ALL=1`,
   add `export NWNX_ITEM_SKIP=n` alongside its other plugin settings. The matching
   `nwnx_item.nss` include must be available to the compiler. Existing Creature,
   Core and other bridge dependencies are still required.
3. In **Controlled Actions**, select the NPC, enable approved actions, and find
   **Inventory, containers and assistance**.
4. Add the exact tag of each permitted chest. In the current test world the chest
   beside the throne is `rq_testchest`. Tags permit every matching container, so
   give restricted chests unique tags.
5. Enable only the capabilities wanted and save. Put the NPC in AUTO.

| Permission | What it permits |
| --- | --- |
| Container tags | Walk to, open and inspect those containers |
| Take / Deposit | Transfer an existing item between the NPC and an approved chest |
| Give | Deliver a carried item to the requesting player or a willing AI NPC |
| Receive | Accept a player-confirmed gift or another AI NPC's delivery |
| Barter | Player-confirmed exchange, or exchange with another opted-in AI NPC |
| Fetch | Collect a known non-stackable item and deliver it; also needs Take and Give |
| Help | Use a carried Cure Light Wounds potion or healing kit on an injured recipient or self |

The recipient AI NPC needs Receive enabled. For two-way NPC barter both NPCs
need Receive and Barter enabled, and both must accept the value of the offer.
The default barter rule is 100%: receive at least as much native item value as
is given away. Two NPCs using 100% can therefore swap equal-value items. The
rule is independent of merchant prices and haggling.

## Try it in game

Stand close, select Speak or address the NPC as usual. Wait for the action to
finish. Inventory interactions have a two-second cooldown; ordinary movement
and gestures retain their 20-second cooldown. A running action still must finish.

- “Please inspect the supply chest beside the throne.” Once the NPC arrives:
  “What is in the chest?”
- “Take the dagger from the chest.” Then: “What are you carrying?”
- “Please give me the dagger.” Check your actual inventory.
- “I'd like to give you an item. Open item exchange.” Select an item in your inventory list,
  leave the NPC side unselected, and confirm.
- “Let's barter.” The window shows both eligible inventories with quantities and native gold values.
  Click an item to select it; **Look** opens its native examination. Choose one
  item on each side and confirm. Neither item moves
  just because the window opens or a row is selected. The value rule is checked
  when confirming. Successful transfers refresh both lists and clear selections;
  **Refresh inventories** discards current selections and rereads actual ownership.
- “Put the dagger back in the supply chest.”
- After inspecting: “Fetch the shortsword and bring it to me.”
- “Deliver your dagger to the innkeeper.” Enable Receive on the innkeeper first.
- With both NPCs configured for barter: “Offer your dagger to the innkeeper in
  exchange for theirs.” Both must carry eligible items.
- Give an NPC a standard Cure Light Wounds potion, take some damage, then ask
  “Could you help with my injuries?” With Help enabled, one real potion is
  consumed and the game rolls `1d8 + 1` healing. A carried healing kit can instead
  be used with “Apply your bandages to me” or “Use the healing kit on yourself”.
  Kits use NWN’s native Heal skill action: the game handles skill checks, kit
  quality and consumption. A treatment attempt can fail; success is not guaranteed.

Opening an unknown chest is one action; collecting or fetching a revealed item
is a subsequent request. This version does not search unknown containers or
continue an open-ended task plan in the background.

## Boundaries and persistence

- Only identified, unequipped, droppable, non-plot, non-cursed items within the
  configured native gold-value ceiling are eligible. Bags containing items are
  excluded. An empty eligible list does not prove the NPC has no other items.
- Only unlocked, untrapped, usable containers without custom OnOpen or OnUsed
  scripts are supported. Opening uses the placeable's open animation after the
  NPC arrives; it does not emulate a player's script event. Scripted chests need
  a future world-specific integration, not removal of their access checks.
- Player inventory is shown only to that player in the exchange window; it is
  not sent to the LLM. The window is a Role Weaver NUI interface, not NWN's
  player-to-player barter UI. It expires after 60 seconds or when permissions,
  distance, mode or other eligibility changes.
- Two-way barter and fetch use single non-stackable objects. One-way gifts,
  taking and depositing can move whole stacks. There is no split-stack UI,
  gold transfer, item creation, resurrection, scroll casting or combat healing.
- Work stays in the current area, inside a configurable 2–40 metre radius, and
  times out after 120 seconds. Combat, death, DM possession, pausing or permission
  revocation interrupts it. Encounter actors cannot start inventory tasks.
- A failed delivery leaves a collected item with the NPC. It does not duplicate
  it or invent a return trip. Two-way swaps attempt compensation if their second
  transfer fails; a compensation failure is reported for DM investigation.
- Actual item persistence belongs to the NWN world. Player transfers request a
  character save. **Role Weaver recovery backups do not save or restore loose
  NPC inventories or chest contents.** Include your world's persistence data in
  backups. Tasks are never replayed after restart. These operations are not a
  crash-atomic database transaction across a custom world's scripts.

## Developer checks

`python -m unittest tests.test_inventory` checks migration, permissions, stale
snapshots, recipient opt-in, privacy and opaque command dispatch.
`tests/inventory_native.nss` is a native regression fixture for a **disposable
copy** of the test world containing `rq_testchest` and `rw_base`. Compile it as
`invtest`, use it only as that copy's module-load script, disable all other module
event hooks, and run with a separate userdata directory and port. It creates
fixture items and NPCs; **never run it in a live world**. Logs contain
`RW_INV_TEST ... PASS/FAIL`. The in-game player exchange window still requires
manual client testing for selection, cancellation and confirmation.


## Equipment and self-use item powers

In Controlled Actions, enable **Equip and unequip carried equipment** for an NPC.
Ask it to equip a carried sword, shield, armour or accessory, or remove it.
The bridge reads legal slots from the module's baseitems table; the engine enforces
proficiency, class and level restrictions. Completion requires observing the actual
slot change. Equipped items remain visible to the NPC but cannot be transferred
until unequipped. No attack permission is granted by equipping a weapon.

For potions, scrolls or other active items, enable **Activate approved item powers
on self** and list the exact lowercase item blueprint resrefs, one per line
(for example `nw_it_mpotion001`). Only real Cast Spell properties are offered.
The native item-use action targets the NPC itself and consumes normal charges.
Review custom scripts and area effects before approving a blueprint. Healing
others continues to use the separate assistance controls. This does not grant
arbitrary hostile targeting, bypass spell restrictions, or create items.

Both settings default off, including for existing installations. Item use reports
observed consumption or an unconfirmed attempt; it never assumes a spell succeeded.
Equipment changes and item powers are currently out-of-combat conversation actions.
