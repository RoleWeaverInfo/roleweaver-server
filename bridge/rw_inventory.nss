// Game-owned exchanges. Gold payments require a separate explicit confirmation.
// No creation/cloning or player inventory scans for the LLM.
#include "rw_inc"
#include "rw_payment"
#include "nwnx_item"
#include "nw_inc_nui"

json RWInvPolicy(object npc) { return JsonParse(GetLocalString(npc,"rw_inventory_policy")); }
int RWInvFlag(object npc,string key) { return GetLocalInt(npc,"rw_inventory_enabled") && RWI(RWInvPolicy(npc),key); }
int RWInvReady(object o)
{ return GetIsObjectValid(o) && !GetIsDM(o) && !GetIsDMPossessed(o) && !GetIsDead(o) && !GetIsInCombat(o)
    && (GetIsPC(o) || GetLocalString(o,"rw_mode")=="auto"); }
string RWInvHealingKind(object item)
{
    if(GetResRef(item)=="nw_it_mpotion001")return "potion";
    if(GetBaseItemType(item)==BASE_ITEM_HEALERSKIT)return "bandage";
    return "";
}
int RWInvSafe(object item,object owner,int maximum,int equipped=FALSE)
{
    if(!GetIsObjectValid(item) || GetObjectType(item)!=OBJECT_TYPE_ITEM || GetItemPossessor(item)!=owner
        || GetPlotFlag(item) || GetItemCursedFlag(item) || !GetDroppableFlag(item) || !GetIdentified(item)
        || GetHasInventory(item) || GetGoldPieceValue(item)>maximum || GetGoldPieceValue(item)<0)return FALSE;
    if(!equipped && GetObjectType(owner)==OBJECT_TYPE_CREATURE)
    { int i; for(i=0;i<18;i++)if(GetItemInSlot(i,owner)==item)return FALSE; }
    return TRUE;
}
// Equipment slots are read from the world's baseitems table, including custom rows.
int RWInvSlot(object item,object npc)
{int s;for(s=0;s<18;s++)if(GetItemInSlot(s,npc)==item)return s;return -1;}
int RWInvSlots(object item)
{
    string raw=GetStringLowerCase(Get2DAString("baseitems","EquipableSlots",GetBaseItemType(item)));
    if(GetStringLeft(raw,2)!="0x")return StringToInt(raw);
    int value=0,i;for(i=2;i<GetStringLength(raw);i++)
    {int digit=FindSubString("0123456789abcdef",GetSubString(raw,i,1));if(digit<0)return 0;value=value*16+digit;}return value;
}
int RWInvUseAllowed(object npc,object item)
{
    if(!RWInvFlag(npc,"use_items"))return FALSE;
    json refs=JsonObjectGet(RWInvPolicy(npc),"usable_resrefs");int i;
    for(i=0;i<JsonGetLength(refs);i++)if(JsonGetString(JsonArrayGet(refs,i))==GetResRef(item))return TRUE;
    return FALSE;
}
itemproperty RWInvPower(object item,int index)
{
    itemproperty ip=GetFirstItemProperty(item);int i=0;
    while(GetIsItemPropertyValid(ip) && i<index){ip=GetNextItemProperty(item);i++;}return ip;
}
int RWInvContainer(object npc,object box)
{
    if(!GetIsObjectValid(box) || GetObjectType(box)!=OBJECT_TYPE_PLACEABLE || !GetHasInventory(box)
        || !GetUseableFlag(box) || GetLocked(box) || GetIsTrapped(box) || GetArea(npc)!=GetArea(box))return FALSE;
    // Native NPC interaction does not open a chest's inventory as it does for a
    // player. Animate only explicitly approved plain containers. Refuse custom
    // interaction hooks rather than bypassing a world's scripted access rules.
    if(GetEventScript(box,EVENT_SCRIPT_PLACEABLE_ON_OPEN)!="" || GetEventScript(box,EVENT_SCRIPT_PLACEABLE_ON_USED)!="")return FALSE;
    json tags=JsonObjectGet(RWInvPolicy(npc),"containers");int i;
    for(i=0;i<JsonGetLength(tags);i++)if(JsonGetString(JsonArrayGet(tags,i))==GetTag(box) && GetTag(box)!="")return TRUE;
    return FALSE;
}
// Item bags are excluded; only loose possessions may cross this boundary.
string RWInvRef(object item)
{
    int serial=GetLocalInt(item,"rw_inventory_serial");
    if(!serial){serial=GetLocalInt(GetModule(),"rw_inventory_serial")+1;SetLocalInt(GetModule(),"rw_inventory_serial",serial);SetLocalInt(item,"rw_inventory_serial",serial);}
    return "i"+IntToString(serial);
}
json RWInvRows(object npc,object owner)
{
    json rows=JsonArray();object item=GetFirstItemInInventory(owner);int scanned=0,slotScan=0,inventoryDone=FALSE;
    while(scanned<146 && JsonGetLength(rows)<32)
    {
        if(!GetIsObjectValid(item))inventoryDone=TRUE;
        if(inventoryDone)
        {if(owner!=npc || slotScan>=18)break;item=GetItemInSlot(slotScan,owner);slotScan++;}
        scanned++;
        int duplicate=FALSE,r;string key=GetIsObjectValid(item)?RWInvRef(item):"";
        for(r=0;r<JsonGetLength(rows);r++)if(RWS(JsonArrayGet(rows,r),"ref")==key)duplicate=TRUE;
        if(!duplicate && RWInvSafe(item,owner,RWI(RWInvPolicy(npc),"max_value"),owner==npc))
        {
            string ref=RWInvRef(item);SetLocalObject(npc,"rw_inv_"+ref,item);
            json row=JsonObject();row=JsonObjectSet(row,"ref",JsonString(ref));
            row=JsonObjectSet(row,"name",JsonString(GetStringLeft(GetName(item),80)));
            row=JsonObjectSet(row,"stackable",JsonInt(StringToInt(Get2DAString("baseitems","Stacking",GetBaseItemType(item)))>1));
            row=JsonObjectSet(row,"quantity",JsonInt(GetItemStackSize(item)));
            row=JsonObjectSet(row,"healing",JsonInt(RWInvHealingKind(item)!=""));
            row=JsonObjectSet(row,"healing_kind",JsonString(RWInvHealingKind(item)));
            row=JsonObjectSet(row,"equipped",JsonInt(owner==npc && RWInvSlot(item,npc)>=0));
            json slots=JsonArray();int slot,mask=RWInvSlots(item);
            for(slot=0;slot<14;slot++)if(mask & (1<<slot))slots=JsonArrayInsert(slots,JsonInt(slot));
            row=JsonObjectSet(row,"slots",slots);
            json powers=JsonArray();itemproperty ip=GetFirstItemProperty(item);int pi=0;
            while(GetIsItemPropertyValid(ip) && pi<64 && JsonGetLength(powers)<16)
            {
                if(owner==npc && RWInvUseAllowed(npc,item) && GetItemPropertyType(ip)==ITEM_PROPERTY_CAST_SPELL)
                {
                    json power=JsonObject();power=JsonObjectSet(power,"index",JsonInt(pi));
                    string label=GetStringByStrRef(StringToInt(Get2DAString("iprp_spells","Name",GetItemPropertySubType(ip))));
                    power=JsonObjectSet(power,"name",JsonString(GetStringLeft(label,80)));powers=JsonArrayInsert(powers,power);
                }
                ip=GetNextItemProperty(item);pi++;
            }
            row=JsonObjectSet(row,"uses",powers);
            rows=JsonArrayInsert(rows,row);
        }
        if(!inventoryDone)item=GetNextItemInInventory(owner);
    }
    return rows;
}
void RWInvScan(object npc)
{
    json old=JsonParse(GetLocalString(npc,"rw_inventory_snapshot"));json oldRows=JsonObjectGet(old,"items");int i,j;
    for(i=0;i<JsonGetLength(oldRows);i++)DeleteLocalObject(npc,"rw_inv_"+RWS(JsonArrayGet(oldRows,i),"ref"));
    json oldBoxes=JsonObjectGet(old,"containers");
    for(i=0;i<JsonGetLength(oldBoxes);i++){oldRows=JsonObjectGet(JsonArrayGet(oldBoxes,i),"items");for(j=0;j<JsonGetLength(oldRows);j++)DeleteLocalObject(npc,"rw_inv_"+RWS(JsonArrayGet(oldRows,j),"ref"));}
    json v=JsonObject();v=JsonObjectSet(v,"items",RWInvRows(npc,npc));json boxes=JsonArray();
    object box=GetLocalObject(npc,"rw_inspected_container");
    if(RWInvContainer(npc,box) && GetDistanceBetween(npc,box)<=3.0 && LineOfSightObject(npc,box) && GetIsOpen(box))
    {
        json c=JsonObject();c=JsonObjectSet(c,"ref",JsonString("v"+IntToString(GetLocalInt(box,"rw_visible_serial"))));
        c=JsonObjectSet(c,"name",JsonString(GetStringLeft(GetName(box),80)));c=JsonObjectSet(c,"items",RWInvRows(npc,box));boxes=JsonArrayInsert(boxes,c);
    }
    v=JsonObjectSet(v,"containers",boxes);SetLocalString(npc,"rw_inventory_snapshot",JsonDump(v));
}
int RWInvSetup(object npc,json cmd)
{
    json p=JsonObjectGet(cmd,"policy");int radius=RWI(p,"radius"),value=RWI(p,"max_value"),ratio=RWI(p,"barter_percent");
    if(!NWNX_Core_PluginExists("NWNX_Item") || radius<2 || radius>40 || value<0 || value>100000 || ratio<25 || ratio>200
        || JsonGetLength(JsonObjectGet(p,"containers"))>30 || GetStringLength(RWS(cmd,"revision"))!=24)return FALSE;
    if(JsonGetType(JsonObjectGet(p,"containers"))!=JSON_TYPE_ARRAY || (RWI(cmd,"enabled")!=0 && RWI(cmd,"enabled")!=1))return FALSE;
    int i;for(i=0;i<JsonGetLength(JsonObjectGet(p,"containers"));i++)
    {json tag=JsonArrayGet(JsonObjectGet(p,"containers"),i);if(JsonGetType(tag)!=JSON_TYPE_STRING || GetStringLength(JsonGetString(tag))<1 || GetStringLength(JsonGetString(tag))>128)return FALSE;}
    SetLocalString(npc,"rw_inventory_policy",JsonDump(p));SetLocalInt(npc,"rw_inventory_enabled",RWI(cmd,"enabled"));
    SetLocalString(npc,"rw_inventory_revision",RWS(cmd,"revision"));return TRUE;
}
object RWInvRecipient(object npc,string ref,string listener)
{ if(ref=="self")return npc; if(ref=="player")return StringToObject(listener); return GetLocalObject(npc,"rw_visible_"+ref); }
int RWInvRecipientOK(object npc,object who)
{
    return RWInvReady(who) && who!=npc && GetArea(who)==GetArea(npc) && !GetIsEnemy(who,npc)
        && (GetIsPC(who) || (GetLocalString(who,"rw_id")!="" && RWInvFlag(who,"receive")));
}
// Both parties must opt in. A native NPC is never stripped of an item merely
// because another model requested it. Their own value rule must also pass.
int RWInvBarterOK(object npc,object who,object give,object offer)
{
    if(!RWInvFlag(npc,"exchange") || !RWInvSafe(give,npc,RWI(RWInvPolicy(npc),"max_value"))
        || !RWInvSafe(offer,who,RWI(RWInvPolicy(npc),"max_value"))
        || GetItemStackSize(give)!=1 || GetItemStackSize(offer)!=1
        || StringToInt(Get2DAString("baseitems","Stacking",GetBaseItemType(give)))>1
        || StringToInt(Get2DAString("baseitems","Stacking",GetBaseItemType(offer)))>1
        || GetGoldPieceValue(offer)*100<GetGoldPieceValue(give)*RWI(RWInvPolicy(npc),"barter_percent"))return FALSE;
    if(!GetIsPC(who) && (!RWInvFlag(who,"exchange") || !RWInvFlag(npc,"receive")
        || !RWInvSafe(give,npc,RWI(RWInvPolicy(who),"max_value")) || !RWInvSafe(offer,who,RWI(RWInvPolicy(who),"max_value"))
        || GetGoldPieceValue(give)*100<GetGoldPieceValue(offer)*RWI(RWInvPolicy(who),"barter_percent")))return FALSE;
    return TRUE;
}
// Move existing objects only. Compensate on a failed second leg, and surface
// compensation failure; do not recreate items or retry the transaction.
int RWInvBarterMove(object npc,object who,object give,object offer)
{
    if(!NWNX_Item_MoveTo(offer,npc))return FALSE;
    if(!RWInvSafe(give,npc,RWI(RWInvPolicy(npc),"max_value")) || !NWNX_Item_MoveTo(give,who))
    {if(!NWNX_Item_MoveTo(offer,who))return -1;return FALSE;}
    return TRUE;
}
// NUI uses per-window script handling, preserving the world's existing NUI hook.
// Lists expose eligible possessions only, directly to the player, never the LLM.
// Stable object mappings are checked again on every selection and confirmation.
json RWInvOptions(object npc,object owner,object pc,string prefix)
{
    json rows=JsonArray();object item=GetFirstItemInInventory(owner);int i=1,scanned=0;
    while(GetIsObjectValid(item) && i<=32 && scanned<128)
    {
        scanned++;
        if(RWInvSafe(item,owner,RWI(RWInvPolicy(npc),"max_value")))
        {
            SetLocalObject(pc,prefix+IntToString(i),item);
            rows=JsonArrayInsert(rows,JsonString(GetStringLeft(GetName(item),65)+" x"+IntToString(GetItemStackSize(item))+" | "+IntToString(GetGoldPieceValue(item))+" gp"));i++;
        }
        item=GetNextItemInInventory(owner);
    }
    SetLocalInt(pc,prefix+"count",i);return rows;
}
json RWInvPanel(string title,string side)
{
    json col=JsonArray();col=JsonArrayInsert(col,NuiHeight(NuiLabel(JsonString(title),JsonInt(0),JsonInt(1)),28.0));
    json cells=JsonArray();
    cells=JsonArrayInsert(cells,NuiListTemplateCell(NuiId(NuiButton(NuiBind(side+"_items")),"select_"+side),0.0,TRUE));
    cells=JsonArrayInsert(cells,NuiListTemplateCell(NuiId(NuiButton(JsonString("Look")),"look_"+side),48.0,FALSE));
    col=JsonArrayInsert(col,NuiHeight(NuiList(cells,NuiBind(side+"_items"),38.0),250.0));
    col=JsonArrayInsert(col,NuiHeight(NuiLabel(NuiBind(side+"_selected"),JsonInt(0),JsonInt(1)),38.0));
    col=JsonArrayInsert(col,NuiHeight(NuiId(NuiButton(JsonString("Clear selection")),"clear_"+side),30.0));
    json sized=JsonArray();int j;for(j=0;j<JsonGetLength(col);j++)sized=JsonArrayInsert(sized,NuiWidth(JsonArrayGet(col,j),390.0));
    return NuiCol(sized);
}
int RWInvExchange(object npc,object pc)
{
    int payment=RWPaymentPending(npc,pc);
    int items=RWInvFlag(npc,"give") || RWInvFlag(npc,"receive") || RWInvFlag(npc,"exchange");
    if(!RWInvReady(npc) || (!payment && !RWInvRecipientOK(npc,pc)) || !GetIsPC(pc) || GetDistanceBetween(npc,pc)>(payment?10.0:3.0) || !LineOfSightObject(npc,pc)
        || (!items && !payment))return FALSE;
    if(NWNX_Creature_GetIsBartering(pc))return FALSE;
    int old=NuiFindWindow(pc,"rwexchange");if(old)NuiDestroy(pc,old);
    json outItems=JsonArray(),inItems=JsonArray();
    SetLocalInt(pc,"rw_trade_out_count",1);SetLocalInt(pc,"rw_trade_in_count",1);
    if(items && RWInvRecipientOK(npc,pc))
    {outItems=RWInvOptions(npc,npc,pc,"rw_trade_out_");inItems=RWInvOptions(npc,pc,pc,"rw_trade_in_");}
    json col=JsonArray();
    col=JsonArrayInsert(col,NuiHeight(NuiLabel(JsonString("Select items below. Nothing moves until you confirm."),JsonInt(0),JsonInt(1)),28.0));
    json panels=JsonArray();panels=JsonArrayInsert(panels,RWInvPanel(GetStringLeft(GetName(npc),40)+" - receive from","out"));
    panels=JsonArrayInsert(panels,RWInvPanel("Your inventory - give to NPC","in"));col=JsonArrayInsert(col,NuiRow(panels));
    col=JsonArrayInsert(col,NuiHeight(NuiLabel(JsonString("Eligible items only (up to 32 each). Click Look to examine. Values are not shop prices."),JsonInt(0),JsonInt(1)),25.0));
    col=JsonArrayInsert(col,NuiHeight(NuiLabel(JsonString("Select one side for a gift, both for barter. Barter requires single non-stackable items."),JsonInt(0),JsonInt(1)),25.0));
    json buttons=JsonArray();buttons=JsonArrayInsert(buttons,NuiWidth(NuiId(NuiButton(JsonString("Confirm transfer / barter")),"confirm"),390.0));
    buttons=JsonArrayInsert(buttons,NuiWidth(NuiId(NuiButton(JsonString("Refresh inventories")),"refresh"),390.0));col=JsonArrayInsert(col,NuiHeight(NuiRow(buttons),35.0));
    if(payment)
    {
        string purpose=RWS(JsonParse(GetLocalString(npc,"rw_payment_policy")),"purpose");
        col=JsonArrayInsert(col,NuiHeight(NuiLabel(JsonString(GetStringLeft(GetName(npc),40)+": "+GetStringLeft(purpose,100)),JsonInt(0),JsonInt(1)),32.0));
        col=JsonArrayInsert(col,NuiHeight(NuiId(NuiButton(JsonString("Confirm payment: "+IntToString(GetLocalInt(pc,"rw_pay_amount"))+" gold to "+GetStringLeft(GetName(npc),40))),"pay"),35.0));
        col=JsonArrayInsert(col,NuiHeight(NuiLabel(JsonString("Gold payment is separate from selected items. Close to decline. Offer expires after 120 seconds."),JsonInt(0),JsonInt(1)),28.0));
    }
    else if(GetLocalInt(npc,"rw_interaction_enabled") && JsonDump(JsonObjectGet(JsonParse(GetLocalString(npc,"rw_payment_policy")),"enabled"))=="true")
    {
        int amount=RWI(JsonParse(GetLocalString(npc,"rw_payment_policy")),"amount");
        col=JsonArrayInsert(col,NuiHeight(NuiId(NuiButton(JsonString("Request gold payment offer (up to "+IntToString(amount)+" gold)")),"request_payment"),35.0));
        col=JsonArrayInsert(col,NuiHeight(NuiLabel(JsonString("Gold is separate from items. Request an offer, then confirm the amount. No gold moves on request."),JsonInt(0),JsonInt(1)),28.0));
    }
    json wide=JsonArray();int widthIndex;for(widthIndex=0;widthIndex<JsonGetLength(col);widthIndex++){json child=JsonArrayGet(col,widthIndex);if(widthIndex!=1 && widthIndex!=4)child=NuiWidth(child,800.0);wide=JsonArrayInsert(wide,child);}col=wide;
    json window=NuiWindow(NuiCol(col),JsonString("Role Weaver - Exchange"),NuiRect(-1.0,-1.0,860.0,640.0),JSON_FALSE,JSON_FALSE,JSON_TRUE,JSON_FALSE,JSON_TRUE);
    int token=NuiCreate(pc,window,"rwexchange","rw_trade_evt");if(!token)return FALSE;
    NuiSetBind(pc,token,"payment_offer",JsonString(GetLocalString(pc,"rw_pay_offer")));
    NuiSetBind(pc,token,"in",JsonInt(0));NuiSetBind(pc,token,"out",JsonInt(0));
    NuiSetBind(pc,token,"in_items",inItems);NuiSetBind(pc,token,"out_items",outItems);
    NuiSetBind(pc,token,"in_selected",JsonString("Giving: nothing selected"));NuiSetBind(pc,token,"out_selected",JsonString("Receiving: nothing selected"));
    SetLocalObject(pc,"rw_trade_npc",npc);SetLocalInt(pc,"rw_trade_epoch",GetLocalInt(npc,"rw_epoch"));
    SetLocalInt(pc,"rw_trade_until",GetLocalInt(GetModule(),"rw_tick")+60);
    SetLocalString(pc,"rw_trade_revision",GetLocalString(npc,"rw_inventory_revision"));return TRUE;
}
int RWInvKind(string kind)
{ return kind=="inspect" || kind=="take" || kind=="deposit" || kind=="give" || kind=="fetch" || kind=="aid" || kind=="exchange" || kind=="swap" || kind=="equip" || kind=="unequip" || kind=="use"; }
int RWInvStart(object npc,json cmd)
{
    if(GetLocalInt(npc,"rw_combat_active") || !GetLocalInt(npc,"rw_inventory_enabled") || !NWNX_Core_PluginExists("NWNX_Item")
        || RWS(cmd,"inventory_revision")!=GetLocalString(npc,"rw_inventory_revision"))return FALSE;
    string kind=RWS(cmd,"action");object dest=OBJECT_INVALID,source=npc;
    object item=GetLocalObject(npc,"rw_inv_"+RWS(cmd,"item"));object who=RWInvRecipient(npc,RWS(cmd,"recipient"),RWS(cmd,"listener"));
    if(kind=="equip" || kind=="unequip" || kind=="use")
    {
        if(!RWInvReady(npc) || RWS(cmd,"recipient")!="self" || !RWInvSafe(item,npc,RWI(RWInvPolicy(npc),"max_value"),TRUE))return FALSE;
        if(kind=="use")
        {
            int power=RWI(cmd,"power");if(power<0 || power>=64 || !RWInvUseAllowed(npc,item))return FALSE;
            itemproperty ip=RWInvPower(item,power);
            if(!GetIsItemPropertyValid(ip) || GetItemPropertyType(ip)!=ITEM_PROPERTY_CAST_SPELL)return FALSE;
            SetLocalInt(npc,"rw_item_power",power);
        }
        else
        {
            if(!RWInvFlag(npc,"equip"))return FALSE;
            int slot=RWI(cmd,"slot");
            if(kind=="equip" && (slot<0 || slot>=14 || !(RWInvSlots(item)&(1<<slot)) || RWInvSlot(item,npc)>=0))return FALSE;
            if(kind=="unequip" && RWInvSlot(item,npc)<0)return FALSE;
            SetLocalInt(npc,"rw_item_slot",slot);
        }
        SetLocalObject(npc,"rw_inventory_item",item);SetLocalObject(npc,"rw_inventory_target",npc);
        SetLocalString(npc,"rw_task_inventory_revision",RWS(cmd,"inventory_revision"));SetLocalInt(npc,"rw_inventory_phase",0);return TRUE;
    }
    if(kind=="exchange")return RWInvExchange(npc,StringToObject(RWS(cmd,"listener")));
    if(kind=="inspect" || kind=="take" || kind=="deposit" || kind=="fetch")
    {
        dest=GetLocalObject(npc,"rw_visible_"+RWS(cmd,"container"));
        if(!RWInvContainer(npc,dest))return FALSE;
        if(kind=="take" || kind=="fetch")source=dest;
        if(kind=="take" && !RWInvFlag(npc,"take"))return FALSE;
        if(kind=="deposit" && !RWInvFlag(npc,"deposit"))return FALSE;
        if(kind=="fetch" && (!RWInvFlag(npc,"fetch") || !RWInvFlag(npc,"take") || !RWInvFlag(npc,"give") || !RWInvRecipientOK(npc,who)))return FALSE;
    }
    else
    {
        dest=who;if(!(kind=="aid" && who==npc && RWInvReady(npc)) && !RWInvRecipientOK(npc,who))return FALSE;
        if(kind=="give" && !RWInvFlag(npc,"give"))return FALSE;
        if(kind=="swap")
        {
            object offer=GetLocalObject(who,"rw_inv_"+RWS(cmd,"offer"));
            if(!RWInvBarterOK(npc,who,item,offer))return FALSE;
            SetLocalObject(npc,"rw_inventory_offer",offer);
            SetLocalString(npc,"rw_inventory_peer_revision",GetLocalString(who,"rw_inventory_revision"));
        }
        if(kind=="aid" && (!RWInvFlag(npc,"heal") || RWInvHealingKind(item)=="" || GetCurrentHitPoints(who)>=GetMaxHitPoints(who)))return FALSE;
    }
    if(kind=="fetch" && (GetItemStackSize(item)!=1 || StringToInt(Get2DAString("baseitems","Stacking",GetBaseItemType(item)))>1))return FALSE;
    if(kind!="inspect" && !RWInvSafe(item,source,RWI(RWInvPolicy(npc),"max_value")))return FALSE;
    if(GetArea(dest)!=GetArea(npc) || !LineOfSightObject(npc,dest) || GetDistanceBetween(npc,dest)>IntToFloat(RWI(RWInvPolicy(npc),"radius")))return FALSE;
    if(kind=="fetch" && GetDistanceBetween(npc,who)>IntToFloat(RWI(RWInvPolicy(npc),"radius")))return FALSE;
    SetLocalObject(npc,"rw_inventory_item",item);SetLocalObject(npc,"rw_inventory_target",dest);SetLocalObject(npc,"rw_inventory_recipient",who);
    SetLocalLocation(npc,"rw_inventory_origin",GetLocation(npc));SetLocalString(npc,"rw_task_inventory_revision",RWS(cmd,"inventory_revision"));
    SetLocalInt(npc,"rw_inventory_phase",0);return TRUE;
}
string RWInvTaskTick(object npc)
{
    string kind=GetLocalString(npc,"rw_action_kind");object dest=GetLocalObject(npc,"rw_inventory_target"),item=GetLocalObject(npc,"rw_inventory_item");
    int tick=GetLocalInt(GetModule(),"rw_tick"),phase=GetLocalInt(npc,"rw_inventory_phase");
    if(GetLocalString(npc,"rw_task_inventory_revision")!=GetLocalString(npc,"rw_inventory_revision"))return "permissions changed";
    if(kind=="equip" || kind=="unequip" || kind=="use")
    {
        if(!RWInvReady(npc))return "interrupted";
        if(phase==4 && kind=="use" && (!GetIsObjectValid(item) || GetItemStackSize(item)<GetLocalInt(npc,"rw_use_count") || GetItemCharges(item)<GetLocalInt(npc,"rw_use_charges")))
        {RWInvScan(npc);return "item consumed or charge spent; effect depends on game rules";}
        if(!RWInvSafe(item,npc,RWI(RWInvPolicy(npc),"max_value"),TRUE))return "item unavailable or protected";
        if(kind!="use" && !RWInvFlag(npc,"equip"))return "equipment permission disabled";
        if(kind=="use" && !RWInvUseAllowed(npc,item))return "item use permission disabled";
        if(phase==4)
        {
            if(kind=="equip" && GetItemInSlot(GetLocalInt(npc,"rw_item_slot"),npc)==item){RWInvScan(npc);return "completed";}
            if(kind=="unequip" && RWInvSlot(item,npc)<0){RWInvScan(npc);return "completed";}
            if(tick>=GetLocalInt(npc,"rw_item_until"))return kind=="use"?"item use attempted; effect not confirmed":"equipment change rejected by game or timed out";
            return "";
        }
        SetLocalInt(npc,"rw_inventory_phase",4);SetLocalInt(npc,"rw_item_until",tick+15);
        AssignCommand(npc,ClearAllActions(TRUE));
        if(kind=="equip")AssignCommand(npc,ActionEquipItem(item,GetLocalInt(npc,"rw_item_slot")));
        else if(kind=="unequip")AssignCommand(npc,ActionUnequipItem(item));
        else
        {
            itemproperty power=RWInvPower(item,GetLocalInt(npc,"rw_item_power"));
            if(!GetIsItemPropertyValid(power) || GetItemPropertyType(power)!=ITEM_PROPERTY_CAST_SPELL)return "item power unavailable";
            SetLocalInt(npc,"rw_use_count",GetItemStackSize(item));SetLocalInt(npc,"rw_use_charges",GetItemCharges(item));
            AssignCommand(npc,ActionUseItemOnObject(item,power,npc,0,TRUE));
        }
        return "";
    }
    if(tick>=GetLocalInt(npc,"rw_action_deadline"))return "timed out; any collected item remains carried";
    if(!GetIsObjectValid(dest) || GetArea(dest)!=GetArea(npc))return "target unavailable; any collected item remains carried";
    location origin=GetLocalLocation(npc,"rw_inventory_origin");float radius=IntToFloat(RWI(RWInvPolicy(npc),"radius"));
    if(GetAreaFromLocation(origin)!=GetArea(npc) || GetDistanceBetweenLocations(origin,GetLocation(npc))>radius+1.0 || GetDistanceBetweenLocations(origin,GetLocation(dest))>radius)return "movement limit reached";
    if(GetDistanceBetween(npc,dest)>2.5)return "";
    if(!LineOfSightObject(npc,dest))return "target blocked";
    int container=(kind=="inspect" || kind=="take" || kind=="deposit" || (kind=="fetch" && phase<2));
    if(container)
    {
        if(!RWInvContainer(npc,dest))return "container locked, trapped or unavailable";
        if(!GetIsOpen(dest))
        { if(!phase){SetLocalInt(npc,"rw_inventory_phase",1);AssignCommand(npc,ClearAllActions(TRUE));AssignCommand(dest,ActionPlayAnimation(ANIMATION_PLACEABLE_OPEN));}return ""; }
        SetLocalObject(npc,"rw_inspected_container",dest);
        if(kind=="inspect"){RWInvScan(npc);return "completed";}
    }
    object owner=npc,receiver=dest;
    if(kind=="take" || (kind=="fetch" && phase<2)){owner=dest;receiver=npc;}
    if(kind=="aid" && phase==3)
    {
        // The engine owns the Heal skill roll and kit consumption. Do not award
        // HP or destroy a second item, and never queue the same treatment twice.
        if(!(dest==npc && RWInvReady(npc)) && !RWInvRecipientOK(npc,dest))return "recipient unavailable";
        if(!GetIsObjectValid(item) || GetItemStackSize(item)<GetLocalInt(npc,"rw_aid_count") || GetItemCharges(item)<GetLocalInt(npc,"rw_aid_charges"))
        {if(GetIsPC(dest))ExportSingleCharacter(dest);RWInvScan(npc);if(GetCurrentHitPoints(dest)>GetLocalInt(npc,"rw_aid_hp"))return "completed";return "kit used; no healing confirmed";}
        if(GetItemPossessor(item)!=npc)return "healing kit no longer carried";
        if(tick>=GetLocalInt(npc,"rw_aid_until"))return "treatment not completed";
        return "";
    }
    if(!RWInvSafe(item,owner,RWI(RWInvPolicy(npc),"max_value")))return "item unavailable or protected";
    if(!container && !(kind=="aid" && dest==npc && RWInvReady(npc)) && !RWInvRecipientOK(npc,dest))return "recipient unavailable";
    if(kind=="swap")
    {
        object offer=GetLocalObject(npc,"rw_inventory_offer");
        if(GetLocalString(npc,"rw_inventory_peer_revision")!=GetLocalString(dest,"rw_inventory_revision") || !RWInvBarterOK(npc,dest,item,offer))return "barter no longer permitted";
        int swapped=RWInvBarterMove(npc,dest,item,offer);
        RWInvScan(npc);RWInvScan(dest);
        if(swapped<0)return "exchange compensation failed; DM attention required";
        if(!swapped)return "barter rejected by game";
        return "completed";
    }
    if(kind=="aid")
    {
        if(GetCurrentHitPoints(dest)>=GetMaxHitPoints(dest))return "no healing needed";
        if(RWInvHealingKind(item)=="bandage")
        {
            SetLocalInt(npc,"rw_inventory_phase",3);SetLocalInt(npc,"rw_aid_count",GetItemStackSize(item));SetLocalInt(npc,"rw_aid_charges",GetItemCharges(item));
            SetLocalInt(npc,"rw_aid_hp",GetCurrentHitPoints(dest));SetLocalInt(npc,"rw_aid_until",tick+30);
            AssignCommand(npc,ClearAllActions(TRUE));AssignCommand(npc,ActionUseSkill(SKILL_HEAL,dest,0,item));return "";
        }
        int count=GetItemStackSize(item);if(count>1)SetItemStackSize(item,count-1);else DestroyObject(item);
        ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectHeal(d8(1)+1),dest);if(GetIsPC(dest))ExportSingleCharacter(dest);RWInvScan(npc);return "completed";
    }
    if(!NWNX_Item_MoveTo(item,receiver))return "transfer rejected by game";
    if(GetIsPC(receiver))ExportSingleCharacter(receiver);
    if(kind=="fetch" && phase<2)
    {
        // Stackable fetches are excluded: a merge can invalidate the item handle.
        object who=GetLocalObject(npc,"rw_inventory_recipient");
        if(!RWInvRecipientOK(npc,who))return "collected; recipient unavailable, item remains carried";
        SetLocalObject(npc,"rw_inventory_target",who);SetLocalInt(npc,"rw_inventory_phase",2);
        AssignCommand(npc,ClearAllActions(TRUE));AssignCommand(npc,ActionMoveToObject(who,FALSE,1.5));return "";
    }
    RWInvScan(npc);return "completed";
}


