#include "rw_inventory"
void main()
{
    object pc=NuiGetEventPlayer();int token=NuiGetEventWindow();
    if(NuiGetWindowId(pc,token)!="rwexchange")return;
    if(NuiGetEventType()=="close")
    {object owner=GetLocalObject(pc,"rw_trade_npc");if(GetLocalString(owner,"rw_action_kind")=="exchange")SetLocalString(owner,"rw_action_status","exchange closed without confirmation");return;}
    if(NuiGetEventType()!="click")return;
    string element=NuiGetEventElement();
    if(element=="request_payment")
    {
        object owner=GetLocalObject(pc,"rw_trade_npc");int tick=GetLocalInt(GetModule(),"rw_tick");
        if(!RWPaymentPlayer(pc,owner,10.0) || GetLocalInt(pc,"rw_trade_epoch")!=GetLocalInt(owner,"rw_epoch")
            || GetLocalInt(pc,"rw_trade_until")<tick || GetLocalInt(pc,"rw_pay_request_at")>tick)return;
        SetLocalInt(pc,"rw_pay_request_at",tick+5);
        json e=RWBase("payment_request",owner);e=JsonObjectSet(e,"listener",JsonString(ObjectToString(pc)));RWEmit(e);
        SendMessageToPC(pc,"Requesting a gold payment offer. No gold has been taken.");return;
    }
    if(element=="pay")
    {
        string offer=JsonGetString(NuiGetBind(pc,token,"payment_offer"));
        RWPaymentConfirm(pc,offer);
        if(!RWPaymentPending(GetLocalObject(pc,"rw_trade_npc"),pc))NuiDestroy(pc,token);
        return;
    }
    if(element!="confirm")
    {
        object owner=GetLocalObject(pc,"rw_trade_npc");
        if(!RWInvReady(owner) || !RWInvReady(pc) || GetArea(owner)!=GetArea(pc) || GetDistanceBetween(pc,owner)>3.0 || !LineOfSightObject(pc,owner)
            || GetLocalInt(pc,"rw_trade_epoch")!=GetLocalInt(owner,"rw_epoch") || GetLocalString(pc,"rw_trade_revision")!=GetLocalString(owner,"rw_inventory_revision")
            || GetLocalInt(pc,"rw_trade_until")<GetLocalInt(GetModule(),"rw_tick"))
        {NuiDestroy(pc,token);SendMessageToPC(pc,"Exchange expired or unavailable. Ask again.");return;}
        if(element=="refresh"){RWInvExchange(owner,pc);return;}
        string side="";if(element=="select_out" || element=="look_out" || element=="clear_out")side="out";
        if(element=="select_in" || element=="look_in" || element=="clear_in")side="in";
        if(side=="")return;
        if(element=="clear_"+side)
        {NuiSetBind(pc,token,side,JsonInt(0));NuiSetBind(pc,token,side+"_selected",JsonString("Nothing selected"));return;}
        int index=NuiGetEventArrayIndex()+1;
        object item=GetLocalObject(pc,"rw_trade_"+side+"_"+IntToString(index));object holder=owner;if(side=="in")holder=pc;
        if(index<1 || index>=GetLocalInt(pc,"rw_trade_"+side+"_count") || !RWInvSafe(item,holder,RWI(RWInvPolicy(owner),"max_value")))
        {SendMessageToPC(pc,"That inventory changed. Refresh the lists.");return;}
        if(element=="look_"+side){AssignCommand(pc,ActionExamine(item));return;}
        NuiSetBind(pc,token,side,JsonInt(index));
        string direction="Receiving: ";if(side=="in")direction="Giving: ";
        NuiSetBind(pc,token,side+"_selected",JsonString(direction+GetStringLeft(GetName(item),45)+" x"+IntToString(GetItemStackSize(item))));return;
    }
    int a=JsonGetInt(NuiGetBind(pc,token,"out")),b=JsonGetInt(NuiGetBind(pc,token,"in"));
    NuiDestroy(pc,token); // one-shot confirmation; a double click cannot transfer twice
    object npc=GetLocalObject(pc,"rw_trade_npc");
    if(GetLocalString(npc,"rw_action_kind")=="exchange")SetLocalString(npc,"rw_action_status","exchange rejected or expired");
    if(!RWInvReady(npc) || !RWInvReady(pc) || GetArea(pc)!=GetArea(npc) || GetDistanceBetween(pc,npc)>3.0 || !LineOfSightObject(pc,npc)
        || GetLocalInt(pc,"rw_trade_epoch")!=GetLocalInt(npc,"rw_epoch") || GetLocalInt(pc,"rw_trade_until")<GetLocalInt(GetModule(),"rw_tick")
        || GetLocalString(pc,"rw_trade_revision")!=GetLocalString(npc,"rw_inventory_revision") || GetIsEnemy(pc,npc)
        || NWNX_Creature_GetIsBartering(pc)) {SendMessageToPC(pc,"Exchange expired or unavailable. Ask again.");return;}
    object give=GetLocalObject(pc,"rw_trade_out_"+IntToString(a)),offer=GetLocalObject(pc,"rw_trade_in_"+IntToString(b));
    int maximum=RWI(RWInvPolicy(npc),"max_value");
    if(a<0 || b<0 || a>=GetLocalInt(pc,"rw_trade_out_count") || b>=GetLocalInt(pc,"rw_trade_in_count") || (!a && !b)
        || (a && !RWInvSafe(give,npc,maximum)) || (b && !RWInvSafe(offer,pc,maximum))) {SendMessageToPC(pc,"Selected items changed or are protected. Nothing exchanged.");return;}
    if((a && !b && !RWInvFlag(npc,"give")) || (b && !a && !RWInvFlag(npc,"receive"))) {SendMessageToPC(pc,"This NPC is not permitted to make that gift transfer.");return;}
    if(a && b && !RWInvBarterOK(npc,pc,give,offer))
    {SendMessageToPC(pc,"Barter requires permitted, non-stackable items and an offer meeting the DM's value rule.");return;}
    int ok=FALSE;
    if(a && b)ok=RWInvBarterMove(npc,pc,give,offer);
    else if(a)ok=NWNX_Item_MoveTo(give,pc);
    else ok=NWNX_Item_MoveTo(offer,npc);
    if(ok<0)
    {SendMessageToPC(pc,"Exchange incomplete: your offered item remains with the NPC. Contact the DM; do not retry blindly.");SetLocalString(npc,"rw_action_status","exchange compensation failed; DM attention required");ExportSingleCharacter(pc);return;}
    if(ok){if(GetLocalString(npc,"rw_action_kind")=="exchange")SetLocalString(npc,"rw_action_status","exchange completed");ExportSingleCharacter(pc);RWInvScan(npc);SendMessageToPC(pc,"Role Weaver: item exchange completed.");RWInvExchange(npc,pc);}
    else SendMessageToPC(pc,"The game rejected the transfer. No exchange completed.");
}
