// Administrative stock commands are separate from model-controlled actions.
int RWStockAllowed(string ref) { return ref=="nw_wswdg001" || ref=="nw_wswss001" || ref=="nw_wswls001" || ref=="nw_wdbqs001" || ref=="nw_wbwsh001" || ref=="nw_waxbt001" || ref=="nw_waxhn001" || ref=="nw_wblcl001" || ref=="nw_wblhw001" || ref=="nw_wbwxl001" || ref=="nw_aarcl001" || ref=="nw_ashsw001" || ref=="nw_it_mpotion001" || ref=="nw_it_mpotion002" || ref=="nw_it_mpotion003"; }
void RWStockAck(object npc,string request,int ok)
{
    json ack=RWBase("ack",npc);ack=JsonObjectSet(ack,"request",JsonString(request));
    RWEmit(JsonObjectSet(ack,"ok",JsonInt(ok)));
}
void RWFinishStockEdit(object npc,object original,object edited,string request,int epoch,string session)
{
    int ok=GetIsObjectValid(npc) && GetIsObjectValid(original) && GetIsObjectValid(edited)
        && GetLocalObject(npc,"rw_shop")==original && GetLocalInt(npc,"rw_epoch")==epoch
        && GetLocalString(GetModule(),"rw_session")==session && !GetIsDMPossessed(npc) && !GetIsDead(npc) && !GetIsInCombat(npc);
    if(ok)
    {
        SetLocalString(edited,"rw_offer_revision",request);
        ok=RWShopSave(npc,edited);
        if(ok)
        {
            SetLocalObject(npc,"rw_shop",edited);SetLocalObject(edited,"rw_shop_owner",npc);SetLocalString(edited,"rw_shop_world",RWWorld());
            SetLocalInt(npc,"rw_stock_revision",GetLocalInt(npc,"rw_stock_revision")+1);DestroyObject(original);
        }
    }
    if(!ok && GetIsObjectValid(edited))DestroyObject(edited);
    SetLocalInt(npc,"rw_stock_editing",FALSE);
    RWStockAck(npc,request,ok);RWEmit(RWShopSnapshot(npc));
}
int RWStockEdit(object npc,json cmd)
{
    object original=GetLocalObject(npc,"rw_shop");string op=RWS(cmd,"operation");
    int quantity=RWI(cmd,"quantity");
    if(RWS(cmd,"world")!=RWWorld() || GetLocalInt(npc,"rw_stock_editing") || !GetLocalInt(npc,"rw_merchant_enabled")
       || !GetIsObjectValid(original) || GetLocalString(npc,"rw_shop_status")!="ready" || GetIsDMPossessed(npc) || GetIsDead(npc) || GetIsInCombat(npc)
       || RWS(cmd,"rules_revision")!=GetLocalString(npc,"rw_merchant_revision") || RWS(cmd,"stock_revision")!=RWStockRevision(npc)
       || GetStringLength(RWS(cmd,"request"))!=24 || !RWConversationInteger(cmd,"quantity"))return FALSE;
    if(op!="add" && op!="remove")return FALSE;
    if(op=="add" && (!RWStockAllowed(RWS(cmd,"item")) || quantity<1 || quantity>20))return FALSE;
    object target=StringToObject(RWS(cmd,"item"));
    if(op=="remove" && (!GetIsObjectValid(target) || GetItemPossessor(target)!=original || GetItemStackSize(target)!=quantity))return FALSE;
    int count=0;object item=GetFirstItemInInventory(original);
    while(GetIsObjectValid(item))
    {
        count++;SetLocalString(item,"rw_stock_token",ObjectToString(item));item=GetNextItemInInventory(original);
    }
    if(op=="add" && count+quantity>100)return FALSE;
    // Work on a campaign copy. Failed edits leave the live inventory untouched.
    if(!RWShopSave(npc,original))return FALSE;
    object edited=RetrieveCampaignObject(RWShopDatabase(),RWShopKey(npc),GetLocation(npc));
    if(!GetIsObjectValid(edited) || GetObjectType(edited)!=OBJECT_TYPE_STORE)return FALSE;
    int ok=TRUE;
    if(op=="add")
    {
        int i;for(i=0;i<quantity;i++)
        {
            item=CreateItemOnObject(RWS(cmd,"item"),edited,1);
            if(!GetIsObjectValid(item))ok=FALSE;else SetIdentified(item,TRUE);
        }
    }
    else
    {
        item=GetFirstItemInInventory(edited);object remove=OBJECT_INVALID;int matches=0;
        while(GetIsObjectValid(item))
        {
            if(GetLocalString(item,"rw_stock_token")==RWS(cmd,"item")){remove=item;matches++;}
            item=GetNextItemInInventory(edited);
        }
        if(matches!=1)ok=FALSE;else DestroyObject(remove);
    }
    if(!ok){DestroyObject(edited);return FALSE;}
    SetLocalInt(npc,"rw_stock_editing",TRUE);
    int epoch=GetLocalInt(npc,"rw_epoch");string session=GetLocalString(GetModule(),"rw_session");string request=RWS(cmd,"request");
    DelayCommand(0.5,RWFinishStockEdit(npc,original,edited,request,epoch,session));
    return TRUE;
}
