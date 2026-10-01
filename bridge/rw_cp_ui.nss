// Reuses the ordinary exchange panel and item protections. Familiar cargo has
// different ownership: its persistent holder is the owner's satchel.
#include "rw_cp_pack"
#include "nwnx_chat"

json RWCPIOptions(object pc,object holder,string side,int maximum,object exclude=OBJECT_INVALID)
{
    json rows=JsonArray();object item=GetFirstItemInInventory(holder);int index=0,scanned=0;
    while(GetIsObjectValid(item) && scanned<2048 && index<32)
    {
        if(RWCPISafe(item,holder,maximum) && !RWCPIContains(exclude,item))
        {
            SetLocalObject(pc,"rw_cpt_"+side+IntToString(index),item);
            SetLocalString(pc,"rw_cpt_"+side+IntToString(index)+"uuid",GetObjectUUID(item));
            SetLocalInt(pc,"rw_cpt_"+side+IntToString(index)+"qty",GetItemStackSize(item));
            rows=JsonArrayInsert(rows,JsonString(GetStringLeft(GetName(item),65)+" x"+IntToString(GetItemStackSize(item))));index++;
        }
        item=GetNextItemInInventory(holder);scanned++;
    }
    SetLocalInt(pc,"rw_cpt_"+side+"count",index);return rows;
}
// An inventory can change while its window remains open. Recheck the real item,
// its stack size and its current side before accepting any click or transfer.
int RWCPISelection(object pc,string side,int index,int maximum)
{
    if(index<0 || index>=GetLocalInt(pc,"rw_cpt_"+side+"count"))return FALSE;
    string key="rw_cpt_"+side+IntToString(index);object item=GetLocalObject(pc,key);
    object pack=GetLocalObject(pc,"rw_cpt_pack"),holder=side=="out"?pack:pc;
    return RWCPISafe(item,holder,maximum)
        && GetObjectUUID(item)==GetLocalString(pc,key+"uuid")
        && GetItemStackSize(item)==GetLocalInt(pc,key+"qty")
        && (side=="out" || !RWCPIContains(pack,item));
}
int RWCPIWindowValid(object pc)
{
    object owner=GetLocalObject(pc,"rw_cpt_owner"),pack=GetLocalObject(pc,"rw_cpt_pack"),familiar=GetLocalObject(pc,"rw_cpt_familiar");
    if(!GetIsPC(pc) || GetIsDM(pc) || GetIsDead(pc) || GetIsInCombat(pc) || !RWCPIPackOwned(owner,pack)
        || GetLocalString(pc,"rw_cpt_session")!=GetLocalString(GetModule(),"rw_session")
        || GetLocalInt(pc,"rw_cpt_until")<=GetLocalInt(GetModule(),"rw_tick") || NWNX_Creature_GetIsBartering(pc))return FALSE;
    // Recovery is owner-only, withdraw-only, and does not need a living familiar.
    if(GetLocalInt(pc,"rw_cpt_recover"))return owner==pc;
    return RWCPIEnabled() && RWCPPreference(owner,"inventory")
        && (pc==owner || (RWCPPreference(owner,"deliver") && RWCPPreference(owner,"movement")))
        && RWCPReady(owner,familiar) && RWCPIRecipient(familiar,pc)
        && GetDistanceBetween(familiar,pc)<=3.0
        && GetLocalInt(pc,"rw_cpt_type")==GetFamiliarCreatureType(owner)
        && GetLocalInt(pc,"rw_cpt_revision")==GetLocalInt(GetModule(),"rw_cpi_revision")
        && GetLocalInt(pc,"rw_cpt_epoch")==GetLocalInt(familiar,"rw_cpi_epoch")
        && GetLocalInt(pc,"rw_cpt_order")==GetLastAssociateCommand(familiar);
}
int RWCPIWindow(object pc,object owner,object familiar,object pack,object offered=OBJECT_INVALID,int recovery=FALSE)
{
    if(!RWCPIPackOwned(owner,pack) || !GetIsPC(pc) || (pc!=owner && !GetIsObjectValid(offered)))return FALSE;
    SetLocalObject(pc,"rw_cpt_owner",owner);SetLocalObject(pc,"rw_cpt_pack",pack);SetLocalObject(pc,"rw_cpt_familiar",familiar);
    SetLocalObject(pc,"rw_cpt_gift",offered);SetLocalInt(pc,"rw_cpt_recover",recovery);
    SetLocalInt(pc,"rw_cpt_type",GetFamiliarCreatureType(owner));SetLocalInt(pc,"rw_cpt_order",GetLastAssociateCommand(familiar));
    SetLocalInt(pc,"rw_cpt_epoch",GetLocalInt(familiar,"rw_cpi_epoch"));
    SetLocalInt(pc,"rw_cpt_revision",GetLocalInt(GetModule(),"rw_cpi_revision"));
    SetLocalInt(pc,"rw_cpt_until",GetLocalInt(GetModule(),"rw_tick")+60);
    SetLocalString(pc,"rw_cpt_session",GetLocalString(GetModule(),"rw_session"));
    if(!RWCPIWindowValid(pc))return FALSE;
    // A refresh must not look like a user closing the active delivery window.
    int old=NuiFindWindow(pc,"rwcpinventory");DeleteLocalInt(pc,"rw_cpt_token");if(old)NuiDestroy(pc,old);
    json col=JsonArray();json outItems=JsonArray(),inItems=JsonArray();int maximum=RWCPIMaximum();
    if(recovery)maximum=100000; // Recover any eligible cargo after a policy reduction.
    SetLocalInt(pc,"rw_cpt_maximum",maximum);
    if(pc!=owner)
    {
        if(!RWCPISafe(offered,pack,maximum))return FALSE;
        SetLocalString(pc,"rw_cpt_gift_uuid",GetObjectUUID(offered));
        SetLocalInt(pc,"rw_cpt_gift_qty",GetItemStackSize(offered));
        col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiLabel(JsonString(GetName(familiar)+" offers you "+GetStringLeft(GetName(offered),65)+" x"+IntToString(GetItemStackSize(offered))+"."),JsonInt(0),JsonInt(1)),65.0),600.0));
        col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiId(NuiButton(JsonString("Accept this item")),"accept"),40.0),600.0));
        col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiLabel(JsonString("Close to decline. No item moves until you accept."),JsonInt(0),JsonInt(1)),45.0),600.0));
    }
    else
    {
        outItems=RWCPIOptions(pc,pack,"out",maximum);
        if(!recovery)inItems=RWCPIOptions(pc,pc,"in",maximum,pack);else SetLocalInt(pc,"rw_cpt_incount",0);
        string help="Choose belongings to give or receive, then confirm. Equipped gear is not listed; unequip it first.";
        if(recovery)help="Recovery only: take belongings back from the familiar satchel. Your inventory is hidden here. Use Open inventory to give items.";
        else if(JsonGetLength(inItems)==0)help="No eligible player items to give. Unequip gear or carry a loose item, then refresh. Bags, protected, unidentified and over-limit items are excluded.";
        if(JsonGetLength(outItems)==0)help+=" The familiar satchel has no eligible items to take back.";
        col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiText(JsonString(help),FALSE,0),72.0),800.0));
        json panels=JsonArray();panels=JsonArrayInsert(panels,RWInvPanel("Familiar satchel - receive from","out"));
        panels=JsonArrayInsert(panels,RWInvPanel("Your inventory - give to familiar","in"));col=JsonArrayInsert(col,NuiRow(panels));
        json buttons=JsonArray();buttons=JsonArrayInsert(buttons,NuiWidth(NuiId(NuiButton(JsonString("Confirm transfer")),"confirm"),390.0));
        buttons=JsonArrayInsert(buttons,NuiWidth(NuiId(NuiButton(JsonString("Refresh inventories")),"refresh"),390.0));
        col=JsonArrayInsert(col,NuiHeight(NuiRow(buttons),35.0));
        col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiLabel(JsonString("Whole stacks; up to 32 eligible items per list. Select one side for a gift. Two-sided swaps require non-stackable items. Your satchel stays with your saved character."),JsonInt(0),JsonInt(1)),65.0),800.0));
    }
    json window=NuiWindow(NuiCol(col),JsonString("Role Weaver - Familiar Inventory"),NuiRect(-1.0,-1.0,pc==owner?860.0:650.0,pc==owner?600.0:240.0),JSON_FALSE,JSON_FALSE,JSON_TRUE,JSON_FALSE,JSON_TRUE);
    int token=NuiCreate(pc,window,"rwcpinventory","rw_cp_trade");if(!token)return FALSE;
    SetLocalInt(pc,"rw_cpt_token",token);
    if(GetIsObjectValid(familiar))DeleteLocalInt(familiar,"rw_cpi_trade_done");
    NuiSetBind(pc,token,"in",JsonInt(-1));NuiSetBind(pc,token,"out",JsonInt(-1));
    NuiSetBind(pc,token,"in_items",inItems);NuiSetBind(pc,token,"out_items",outItems);
    NuiSetBind(pc,token,"in_selected",JsonString("Giving: nothing selected"));NuiSetBind(pc,token,"out_selected",JsonString("Receiving: nothing selected"));
    return TRUE;
}
void RWCPITradeEvent()
{
    object pc=NuiGetEventPlayer();int token=NuiGetEventWindow();
    if(NuiGetWindowId(pc,token)!="rwcpinventory" || token!=GetLocalInt(pc,"rw_cpt_token"))return;
    object owner=GetLocalObject(pc,"rw_cpt_owner"),pack=GetLocalObject(pc,"rw_cpt_pack"),familiar=GetLocalObject(pc,"rw_cpt_familiar");
    if(NuiGetEventType()=="close")
    {DeleteLocalInt(pc,"rw_cpt_token");SetLocalInt(familiar,"rw_cpi_trade_done",TRUE);return;}
    if(NuiGetEventType()!="click")return;
    if(!RWCPIWindowValid(pc))
    {NuiDestroy(pc,token);SendMessageToPC(pc,"This familiar exchange has expired. No items moved. Ask again.");return;}
    string element=NuiGetEventElement();int maximum=GetLocalInt(pc,"rw_cpt_maximum");
    if(pc!=owner)
    {
        if(element!="accept")return;
        object gift=GetLocalObject(pc,"rw_cpt_gift");
        DeleteLocalInt(pc,"rw_cpt_token");NuiDestroy(pc,token);
        SetLocalInt(familiar,"rw_cpi_trade_done",TRUE);
        int ok=FALSE;
        if(GetIsObjectValid(gift) && GetObjectUUID(gift)==GetLocalString(pc,"rw_cpt_gift_uuid")
            && GetItemStackSize(gift)==GetLocalInt(pc,"rw_cpt_gift_qty"))ok=RWCPIMove(gift,pack,pc,maximum);
        RWCPISave(owner,pc);
        RWCPIStatus(familiar,ok?"Delivery accepted and item transferred.":"Delivery failed; item was unavailable or transfer rejected.");
        SendMessageToPC(pc,ok?"You received the offered item.":"That item is no longer available. No transfer completed.");
        if(ok)NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK,"*Hands over the offered belongings.*",familiar);
        return;
    }
    if(element=="refresh"){RWCPIWindow(pc,owner,familiar,pack,OBJECT_INVALID,GetLocalInt(pc,"rw_cpt_recover"));return;}
    if(element!="confirm")
    {
        string side="";if(element=="select_out" || element=="look_out" || element=="clear_out")side="out";
        if(element=="select_in" || element=="look_in" || element=="clear_in")side="in";
        if(side=="")return;
        if(element=="clear_"+side){NuiSetBind(pc,token,side,JsonInt(-1));NuiSetBind(pc,token,side+"_selected",JsonString("Nothing selected"));return;}
        int index=NuiGetEventArrayIndex();object holder=side=="out"?pack:pc;
        object item=GetLocalObject(pc,"rw_cpt_"+side+IntToString(index));
        if(!RWCPISelection(pc,side,index,maximum))
        {SendMessageToPC(pc,"The inventory changed. Refresh the lists.");return;}
        if(element=="look_"+side){AssignCommand(pc,ActionExamine(item));return;}
        NuiSetBind(pc,token,side,JsonInt(index));NuiSetBind(pc,token,side+"_selected",JsonString((side=="out"?"Receiving: ":"Giving: ")+GetStringLeft(GetName(item),55)));return;
    }
    int a=JsonGetInt(NuiGetBind(pc,token,"out")),b=JsonGetInt(NuiGetBind(pc,token,"in"));
    DeleteLocalInt(pc,"rw_cpt_token");NuiDestroy(pc,token); // consume before moving anything
    object give=GetLocalObject(pc,"rw_cpt_out"+IntToString(a)),offer=GetLocalObject(pc,"rw_cpt_in"+IntToString(b));
    if(a< -1 || b< -1 || (a<0 && b<0) || a>=GetLocalInt(pc,"rw_cpt_outcount") || b>=GetLocalInt(pc,"rw_cpt_incount")
        || (a>=0 && !RWCPISelection(pc,"out",a,maximum)) || (b>=0 && !RWCPISelection(pc,"in",b,maximum)) || (b>=0 && GetLocalInt(pc,"rw_cpt_recover")))
    {SendMessageToPC(pc,"Selected items changed or are protected. Nothing transferred.");return;}
    int result=FALSE;
    if(a>=0 && b>=0)result=RWCPISwap(pack,pc,give,offer,maximum,TRUE);
    else if(a>=0)result=RWCPIMove(give,pack,pc,maximum);
    else result=RWCPIMove(offer,pc,pack,maximum);
    RWCPISave(owner);
    if(result<0){SendMessageToPC(pc,"Transfer only partly completed. Check both inventories; do not repeat blindly.");RWCPIStatus(familiar,"Exchange compensation failed; inspect both inventories.");return;}
    SendMessageToPC(pc,result?"Familiar item transfer completed.":"The game rejected this transfer. No exchange completed.");
    if(result)RWCPIStatus(familiar,"Owner confirmed an item exchange; inventories updated.");
    RWCPIWindow(pc,owner,familiar,pack,OBJECT_INVALID,GetLocalInt(pc,"rw_cpt_recover"));
}
