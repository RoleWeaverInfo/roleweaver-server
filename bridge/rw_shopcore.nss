// Shop definitions shared by merchant and administrative stock helpers.
#include "rw_core"
#include "nwnx_player"
// Dedicated, finite, fixed-price test shop; normal engine transactions own gold/item transfers.
string RWShopDatabase() { return "rw_shops_"+RWWorld(); }
string RWShopKey(object npc) { return "stock_"+GetLocalString(npc,"rw_id"); }
int RWShopSave(object npc,object shop)
{
    int ok=StoreCampaignObject(RWShopDatabase(),RWShopKey(npc),shop);
    if(ok) SetCampaignInt(RWShopDatabase(),"init_"+GetLocalString(npc,"rw_id"),1);
    SetLocalString(npc,"rw_shop_status",ok?"ready":"stock save failed");
    return ok;
}
object RWShopEnsure(object npc)
{
    object shop=GetLocalObject(npc,"rw_shop");
    if(GetIsObjectValid(shop)) return shop;
    shop=RetrieveCampaignObject(RWShopDatabase(),RWShopKey(npc),GetLocation(npc));
    if(!GetIsObjectValid(shop))
    {
        if(GetCampaignInt(RWShopDatabase(),"init_"+GetLocalString(npc,"rw_id")))
        {SetLocalString(npc,"rw_shop_status","saved store unavailable; not restocked");return OBJECT_INVALID;}
        shop=CreateObject(OBJECT_TYPE_STORE,"rw_shop",GetLocation(npc));
        if(!GetIsObjectValid(shop)) {SetLocalString(npc,"rw_shop_status","missing store blueprint");return OBJECT_INVALID;}
        int ok=TRUE;
        if(!GetIsObjectValid(CreateItemOnObject("nw_wswdg001",shop)))ok=FALSE;
        if(!GetIsObjectValid(CreateItemOnObject("nw_wswss001",shop)))ok=FALSE;
        if(!GetIsObjectValid(CreateItemOnObject("nw_wswls001",shop)))ok=FALSE;
        if(!GetIsObjectValid(CreateItemOnObject("nw_wdbqs001",shop)))ok=FALSE;
        if(!GetIsObjectValid(CreateItemOnObject("nw_wbwsh001",shop)))ok=FALSE;
        if(!ok){DestroyObject(shop);SetLocalString(npc,"rw_shop_status","weapon blueprint unavailable");return OBJECT_INVALID;}
    }
    if(GetObjectType(shop)!=OBJECT_TYPE_STORE){SetLocalString(npc,"rw_shop_status","saved object is not a store");return OBJECT_INVALID;}
    SetTag(shop,"rw_shop_"+GetLocalString(npc,"rw_id"));
    SetLocalObject(shop,"rw_shop_owner",npc);SetLocalString(shop,"rw_shop_world",RWWorld());
    SetLocalObject(npc,"rw_shop",shop);
    RWShopSave(npc,shop);
    return shop;
}
// Percentage-based haggling. Native store prices round down to whole gold.
json RWHaggleRules(object npc)
{
    string raw=GetLocalString(npc,"rw_haggle_rules");
    if(raw=="")return JsonParse("{\"enabled\":1,\"chance\":50,\"discount\":5,\"cooldown\":600}");
    return JsonParse(raw);
}
int RWApplyMerchantRules(object npc,json p,string revision)
{
    if(GetLocalInt(npc,"rw_stock_editing") || (revision!="defaults-v2" && GetStringLength(revision)!=24))return FALSE;
    if(!RWConversationInteger(p,"enabled") || !RWConversationInteger(p,"chance") || !RWConversationInteger(p,"discount") || !RWConversationInteger(p,"cooldown"))return FALSE;
    if(RWI(p,"enabled")<0 || RWI(p,"enabled")>1 || RWI(p,"chance")<0 || RWI(p,"chance")>100
       || RWI(p,"discount")<0 || RWI(p,"discount")>10 || RWI(p,"cooldown")<60 || RWI(p,"cooldown")>86400)return FALSE;
    SetLocalString(npc,"rw_haggle_rules",JsonDump(p));SetLocalString(npc,"rw_merchant_revision",revision);return TRUE;
}
string RWStockRevision(object npc)
{
    return ObjectToString(GetLocalObject(npc,"rw_shop"))+":"+IntToString(GetLocalInt(npc,"rw_stock_revision"));
}
int RWHaggleDiscount(int roll,object npc=OBJECT_INVALID)
{
    if(roll<1 || roll>100)return 0;
    json p=RWHaggleRules(npc);if(!RWI(p,"enabled") || roll>RWI(p,"chance"))return 0;
    return RWI(p,"discount");
}
int RWShopPrice(int base,int discount)
{
    if(discount<0 || discount>10)discount=0;
    if(base<=0)return 0;
    int price=(base/100)*(100-discount)+((base%100)*(100-discount))/100;
    if(price<1)price=1;
    return price;
}
string RWHaggleKey(object npc,object pc)
{
    string account=GetPCPublicCDKey(pc);
    if(account=="")return "";
    return RWKey("haggle:"+GetLocalString(npc,"rw_id")+":"+GetLocalString(npc,"rw_merchant_revision")+":"+GetLocalString(GetLocalObject(npc,"rw_shop"),"rw_offer_revision")+":"+account);
}
json RWHaggleRead(string key)
{
    if(key=="")return JsonObject();
    int result=NWNX_Redis_GET(key);int kind=NWNX_Redis_GetResultType(result);
    string raw=NWNX_Redis_GetResultAsString(result);
    if(kind==NWNX_REDIS_RESULT_NULL)return JsonObject();
    json offer=JsonParse(raw);
    if(RWI(offer,"version")!=2 || (RWI(offer,"discount")<0 || RWI(offer,"discount")>10))return JsonObject();
    int ttl=NWNX_Redis_GetResultAsInt(NWNX_Redis_TTL(key));
    if(ttl<1 || ttl>86400)return JsonObject();
    return JsonObjectSet(offer,"seconds_remaining",JsonInt(ttl));
}
json RWHaggleSave(string key,int roll,object npc=OBJECT_INVALID)
{
    json old=RWHaggleRead(key);if(RWI(old,"version")==2)return old;
    if(key=="" || roll<1 || roll>100)return JsonObject();
    json v=JsonObject();v=JsonObjectSet(v,"version",JsonInt(2));
    v=JsonObjectSet(v,"roll",JsonInt(roll));
    json rules=RWHaggleRules(npc);
    v=JsonObjectSet(v,"chance",JsonInt(RWI(rules,"chance")));
    v=JsonObjectSet(v,"won",JsonInt(RWI(rules,"enabled") && roll<=RWI(rules,"chance")));
    v=JsonObjectSet(v,"discount",JsonInt(RWHaggleDiscount(roll,npc)));
    string ok=NWNX_Redis_GetResultAsString(NWNX_Redis_SETEX(key,RWI(rules,"cooldown"),JsonDump(v)));
    if(ok!="OK")return JsonObject();
    return RWHaggleRead(key);
}
json RWShopSnapshot(object npc)
{
    json v=RWBase("merchant_stock",npc);json items=JsonArray();
    v=JsonObjectSet(v,"rules_revision",JsonString(GetLocalString(npc,"rw_merchant_revision")));
    v=JsonObjectSet(v,"stock_revision",JsonString(RWStockRevision(npc)));
    string status=GetLocalString(npc,"rw_shop_status");
    if(!GetLocalInt(npc,"rw_merchant_enabled"))status="disabled";
    object shop=GetLocalObject(npc,"rw_shop");
    if(GetLocalInt(npc,"rw_stock_editing"))status="updating stock";
    if(status=="ready" && !GetIsObjectValid(shop))status="store unavailable";
    if(status=="ready")
    {
        object item=GetFirstItemInInventory(shop);int count=0;
        while(GetIsObjectValid(item) && count<100)
        {
            json row=JsonObject();row=JsonObjectSet(row,"name",JsonString(GetName(item)));
            row=JsonObjectSet(row,"quantity",JsonInt(GetItemStackSize(item)));
            row=JsonObjectSet(row,"price",JsonInt(RWShopPrice(GetGoldPieceValue(item),0)));
            row=JsonObjectSet(row,"resref",JsonString(GetResRef(item)));
            row=JsonObjectSet(row,"item",JsonString(ObjectToString(item)));
            items=JsonArrayInsert(items,row);count++;item=GetNextItemInInventory(shop);
        }
    }
    v=JsonObjectSet(v,"status",JsonString(status));return JsonObjectSet(v,"items",items);
}
string RWShopPriceStamp(object npc,object pc)
{
    json offer=RWHaggleRead(RWHaggleKey(npc,pc));
    return GetLocalString(npc,"rw_merchant_revision")+"|"+RWStockRevision(npc)+"|"+IntToString(RWI(offer,"discount"));
}
json RWShopQuote(object npc,object pc)
{
    json v=RWShopSnapshot(npc);json offer=RWHaggleRead(RWHaggleKey(npc,pc));
    v=JsonObjectSet(v,"listener",JsonString(ObjectToString(pc)));
    v=JsonObjectSet(v,"price_stamp",JsonString(RWShopPriceStamp(npc,pc)));
    v=JsonObjectSet(v,"haggle",offer);int discount=RWI(offer,"discount");
    json items=JsonObject();items=JsonArray();object shop=GetLocalObject(npc,"rw_shop");
    object item=GetFirstItemInInventory(shop);int count=0;
    while(GetIsObjectValid(item) && count<100 && RWS(v,"status")=="ready")
    {
        json row=JsonObject();row=JsonObjectSet(row,"name",JsonString(GetName(item)));
        row=JsonObjectSet(row,"quantity",JsonInt(GetItemStackSize(item)));
        row=JsonObjectSet(row,"price",JsonInt(RWShopPrice(GetGoldPieceValue(item),discount)));
        items=JsonArrayInsert(items,row);count++;item=GetNextItemInInventory(shop);
    }
    return JsonObjectSet(v,"items",items);
}
void RWShopTick(object npc)
{
    if(GetLocalInt(npc,"rw_merchant_enabled") && !GetLocalInt(npc,"rw_stock_editing")) {object shop=RWShopEnsure(npc);if(GetIsObjectValid(shop))RWShopSave(npc,shop);}
    RWEmit(RWShopSnapshot(npc));
}
int RWShopCustomer(object npc,object pc)
{
    return GetIsObjectValid(npc) && GetIsObjectValid(pc) && GetIsPC(pc) && !GetIsDM(pc) && !GetIsDMPossessed(pc) && !GetIsDead(pc)
        && !GetLocalInt(npc,"rw_stock_editing") && GetLocalInt(npc,"rw_merchant_enabled") && GetLocalString(npc,"rw_shop_status")=="ready"
        && GetLocalString(npc,"rw_mode")=="auto" && !GetIsDMPossessed(npc) && !GetIsDead(npc) && !GetIsInCombat(npc)
        && RWCanHear(pc,npc,6.0);
}
void RWShopFinishOpen(object npc,object pc,int ticket,int epoch,string session)
{
    if(!GetIsObjectValid(pc) || GetLocalInt(pc,"rw_shop_open_ticket")!=ticket
       || GetLocalInt(npc,"rw_epoch")!=epoch || GetLocalString(GetModule(),"rw_session")!=session
       || !RWShopCustomer(npc,pc))return;
    object shop=GetLocalObject(npc,"rw_shop");if(!GetIsObjectValid(shop))return;
    SetLocalString(pc,"rw_shop_session",session);
    SetLocalObject(pc,"rw_shop_authorized",shop);
    json offer=RWHaggleRead(RWHaggleKey(npc,pc));int discount=RWI(offer,"discount");
    SetLocalInt(pc,"rw_shop_discount",discount);
    SetLocalString(pc,"rw_shop_rules",GetLocalString(npc,"rw_merchant_revision"));
    OpenStore(shop,pc,-discount,0);
}
int RWShopOpen(object npc,object pc)
{
    if(!GetIsObjectValid(GetLocalObject(npc,"rw_shop")) || !RWShopCustomer(npc,pc))return FALSE;
    DeleteLocalObject(pc,"rw_shop_authorized");
    NWNX_Player_CloseStore(pc);
    int ticket=GetLocalInt(pc,"rw_shop_open_ticket")+1;SetLocalInt(pc,"rw_shop_open_ticket",ticket);
    int epoch=GetLocalInt(npc,"rw_epoch");string session=GetLocalString(GetModule(),"rw_session");
    DelayCommand(0.5,RWShopFinishOpen(npc,pc,ticket,epoch,session));
    return TRUE;
}

void RWShopDetach(object npc)
{
    object shop=GetLocalObject(npc,"rw_shop");
    if(GetIsObjectValid(shop)){RWShopSave(npc,shop);DestroyObject(shop);}
    DeleteLocalObject(npc,"rw_shop");SetLocalInt(npc,"rw_merchant_enabled",FALSE);
}

int RWShopHaggle(object npc,object pc)
{
    if(!RWShopCustomer(npc,pc) || !RWI(RWHaggleRules(npc),"enabled"))return FALSE;
    string key=RWHaggleKey(npc,pc);if(key=="")return FALSE;
    json offer=RWHaggleRead(key);
    if(RWI(offer,"version")!=2)offer=RWHaggleSave(key,d100(),npc);
    if(RWI(offer,"version")!=2){SendMessageToPC(pc,"Haggling is temporarily unavailable. No offer was granted.");return FALSE;}
    string result="No discount this time.";int discount=RWI(offer,"discount");
    if(RWI(offer,"won"))result="Success: "+IntToString(discount)+"% off normal prices, rounded down to whole gold (minimum 1).";
    SendMessageToPC(pc,GetName(npc)+" — Haggle roll: "+IntToString(RWI(offer,"roll"))+" out of 100; success chance "+IntToString(RWI(offer,"chance"))+"%. "+result+" This result is kept for "+IntToString(RWI(offer,"seconds_remaining"))+" seconds; asking again will not reroll or stack discounts.");
    return RWShopOpen(npc,pc);
}
