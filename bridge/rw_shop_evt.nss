#include "rw_inc"
#include "nwnx_events"
void main()
{
    string evt=NWNX_Events_GetCurrentEvent();
    object shop=StringToObject(NWNX_Events_GetEventData("STORE"));
    if(GetLocalString(shop,"rw_shop_world")!=RWWorld())return;
    object npc=GetLocalObject(shop,"rw_shop_owner");object pc=OBJECT_SELF;
    if(FindSubString(evt,"_BEFORE")>=0)
    {
        object item=StringToObject(NWNX_Events_GetEventData("ITEM"));
        json offer=RWHaggleRead(RWHaggleKey(npc,pc));int discount=RWI(offer,"discount");
        int price=StringToInt(NWNX_Events_GetEventData("PRICE"));
        int ok=RWShopCustomer(npc,pc) && GetLocalObject(npc,"rw_shop")==shop
            && GetLocalObject(pc,"rw_shop_authorized")==shop && GetLocalString(pc,"rw_shop_session")==GetLocalString(GetModule(),"rw_session")
            && evt=="NWNX_ON_STORE_REQUEST_BUY_BEFORE" && GetIsObjectValid(item) && GetItemPossessor(item)==shop
            && GetLocalString(pc,"rw_shop_rules")==GetLocalString(npc,"rw_merchant_revision") && discount==GetLocalInt(pc,"rw_shop_discount") && price==RWShopPrice(GetGoldPieceValue(item),discount) && price>=0 && GetGold(pc)>=price && GetBaseItemFitsInInventory(GetBaseItemType(item),pc);
        if(!ok){NWNX_Events_SkipEvent();NWNX_Events_SetEventResult("0");SendMessageToPC(pc,"This purchase is unavailable. Speak to the merchant nearby and reopen the shop. This shop does not buy items yet.");}
    }
    else
    {
        // Persist the actual resulting inventory, not the event RESULT (which is not a full transaction receipt).
        if(GetIsObjectValid(npc) && GetLocalObject(npc,"rw_shop")==shop && !GetLocalInt(npc,"rw_stock_editing")){SetLocalInt(npc,"rw_stock_revision",GetLocalInt(npc,"rw_stock_revision")+1);RWShopSave(npc,shop);RWEmit(RWShopSnapshot(npc));}
    }
}
