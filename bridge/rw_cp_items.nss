// Short, owner-authorized inventory errands. Native object references remain
// here; the model receives only offered action IDs and readable descriptions.
#include "rw_cp_ui"

json RWCPIAdd(json options,string verb,string description,object item=OBJECT_INVALID,object target=OBJECT_INVALID,object offer=OBJECT_INVALID)
{
    if(JsonGetLength(options)>=96)return options;
    json row=JsonObject();row=JsonObjectSet(row,"id",JsonString("cpinv:"+IntToString(JsonGetLength(options))));
    row=JsonObjectSet(row,"description",JsonString(GetStringLeft(description,240)));
    row=JsonObjectSet(row,"verb",JsonString(verb));row=JsonObjectSet(row,"item",JsonString(ObjectToString(item)));
    row=JsonObjectSet(row,"target",JsonString(ObjectToString(target)));row=JsonObjectSet(row,"offer",JsonString(ObjectToString(offer)));
    if(GetIsObjectValid(item))row=JsonObjectSet(row,"item_uuid",JsonString(GetObjectUUID(item)));
    if(GetIsObjectValid(target))row=JsonObjectSet(row,"target_uuid",JsonString(GetObjectUUID(target)));
    if(GetIsObjectValid(offer))row=JsonObjectSet(row,"offer_uuid",JsonString(GetObjectUUID(offer)));
    return JsonArrayInsert(options,row);
}
json RWCPIItemRow(object item,int index)
{
    json row=JsonObject();row=JsonObjectSet(row,"ref",JsonString("i"+IntToString(index+1)));
    row=JsonObjectSet(row,"name",JsonString(GetStringLeft(GetName(item),80)));
    row=JsonObjectSet(row,"quantity",JsonInt(GetItemStackSize(item)));
    row=JsonObjectSet(row,"stackable",JsonInt(StringToInt(Get2DAString("baseitems","Stacking",GetBaseItemType(item)))>1));
    return row;
}
json RWCPIObserve(json payload,object owner,object familiar)
{
    object pack=RWCPIPack(owner);json view=JsonObject(),options=JsonArray(),rows=JsonArray(),ground=JsonArray(),boxes=JsonArray();
    int available=RWCPIEnabled() && RWCPPreference(owner,"inventory") && RWCPReady(owner,familiar) && RWCPIPackOwned(owner,pack);
    view=JsonObjectSet(view,"available",JsonInt(available));
    if(available)
    {
        options=RWCPIAdd(options,"exchange","Open your satchel exchange window for your owner; nothing moves until they confirm.",OBJECT_INVALID,owner);
        // Loose world items and approved plain containers, bounded by visibility.
        object o=GetFirstObjectInArea(GetArea(familiar));int scanned=0,groundCount=0,boxCount=0;
        while(GetIsObjectValid(o) && scanned<1024 && groundCount+boxCount<24)
        {
            if(groundCount<16 && RWCPIGround(familiar,o))
            {
                ground=JsonArrayInsert(ground,RWCPIItemRow(o,groundCount));groundCount++;
                options=RWCPIAdd(options,"pickup","Walk to and collect "+GetStringLeft(GetName(o),65)+" from the ground into your satchel.",o,o);
                options=RWCPIAdd(options,"fetch_ground","Fetch "+GetStringLeft(GetName(o),65)+" from the ground and bring it to your owner.",o,o);
            }
            else if(boxCount<8 && RWCPIContainer(familiar,o))
            {
                options=RWCPIAdd(options,"inspect","Walk to, open and inspect "+GetStringLeft(GetName(o),65)+".",OBJECT_INVALID,o);boxCount++;
                if(GetLocalObject(familiar,"rw_cpi_inspected")==o && GetIsOpen(o) && GetDistanceBetween(familiar,o)<=3.0)
                {
                    json contents=JsonArray();object contained=GetFirstItemInInventory(o);int n=0,scan=0;
                    while(GetIsObjectValid(contained) && n<16 && scan<2048)
                    {
                        if(RWCPISafe(contained,o,RWCPIMaximum()))
                        {
                            contents=JsonArrayInsert(contents,RWCPIItemRow(contained,n));n++;
                            options=RWCPIAdd(options,"take","Collect "+GetStringLeft(GetName(contained),55)+" from "+GetStringLeft(GetName(o),55)+" into your satchel.",contained,o);
                            options=RWCPIAdd(options,"fetch","Fetch "+GetStringLeft(GetName(contained),55)+" from "+GetStringLeft(GetName(o),55)+" and bring it to your owner.",contained,o);
                        }
                        contained=GetNextItemInInventory(o);scan++;
                    }
                    json box=JsonObject();box=JsonObjectSet(box,"name",JsonString(GetStringLeft(GetName(o),80)));box=JsonObjectSet(box,"items",contents);boxes=JsonArrayInsert(boxes,box);
                }
            }
            o=GetNextObjectInArea(GetArea(familiar));scanned++;
        }
        object item=GetFirstItemInInventory(pack);int count=0,itemScan=0;
        while(GetIsObjectValid(item) && count<32 && itemScan<2048)
        {
            if(RWCPISafe(item,pack,RWCPIMaximum()))
            {
                rows=JsonArrayInsert(rows,RWCPIItemRow(item,count));count++;
                if(count<=16)options=RWCPIAdd(options,"give","Bring "+GetStringLeft(GetName(item),65)+" to your owner.",item,owner);
            }
            item=GetNextItemInInventory(pack);itemScan++;
        }
        // Other players see only a particular offered item and must accept it.
        // NPC barter is allowed only by that NPC's existing inventory policy.
        o=GetFirstObjectInArea(GetArea(familiar));scanned=0;int peers=0;
        while(GetIsObjectValid(o) && scanned<1024 && peers<4)
        {
            if(o!=owner && GetObjectType(o)==OBJECT_TYPE_CREATURE && RWCPIRecipient(familiar,o) && RWAreaCreatureVisible(familiar,o))
            {
                string name=GetIsPC(o)?"the nearby traveler ("+IntToString(FloatToInt(GetDistanceBetween(familiar,o)))+" metres "+RWVisibleBearing(familiar,o)+")":GetStringLeft(GetName(o),65);
                item=GetFirstItemInInventory(pack);int n=0,scan=0;
                while(GetIsObjectValid(item) && n<4 && scan<2048)
                {
                    if(RWCPISafe(item,pack,RWCPIMaximum()))
                    {
                        n++;
                        options=RWCPIAdd(options,"give","Deliver "+GetStringLeft(GetName(item),55)+" to "+name+(GetIsPC(o)?"; they must confirm acceptance.":"."),item,o);
                        if(!GetIsPC(o) && RWInvFlag(o,"exchange"))
                        {
                            object offered=GetFirstItemInInventory(o);int offers=0,offerScan=0;
                            while(GetIsObjectValid(offered) && offers<4 && offerScan<2048)
                            {
                                if(RWCPISwapOK(pack,o,item,offered,RWCPIMaximum(),FALSE))
                                {options=RWCPIAdd(options,"swap","Offer "+GetStringLeft(GetName(item),45)+" to "+name+" in exchange for "+GetStringLeft(GetName(offered),45)+".",item,o,offered);offers++;}
                                offered=GetNextItemInInventory(o);offerScan++;
                            }
                        }
                    }
                    item=GetNextItemInInventory(pack);scan++;
                }
                peers++;
            }
            o=GetNextObjectInArea(GetArea(familiar));scanned++;
        }
    }
    json permitted=JsonArray();int j;
    for(j=0;j<JsonGetLength(options);j++)
    {
        json candidate=JsonArrayGet(options,j);
        if(RWCPIWorkAllowed(owner,candidate)
            && (RWS(candidate,"verb")!="exchange" || RWCPPreference(owner,"movement") || GetDistanceBetween(owner,familiar)<=2.5))
            permitted=JsonArrayInsert(permitted,candidate);
    }
    options=permitted;SetLocalString(familiar,"rw_cpi_choices",JsonDump(options));
    json publicOptions=JsonArray();int i;
    for(i=0;i<JsonGetLength(options);i++)
    {json row=JsonArrayGet(options,i),p=JsonObject();p=JsonObjectSet(p,"id",JsonObjectGet(row,"id"));p=JsonObjectSet(p,"description",JsonObjectGet(row,"description"));publicOptions=JsonArrayInsert(publicOptions,p);}
    view=JsonObjectSet(view,"items",rows);view=JsonObjectSet(view,"ground",ground);view=JsonObjectSet(view,"containers",boxes);view=JsonObjectSet(view,"choices",publicOptions);
    view=JsonObjectSet(view,"status",JsonString(GetLocalString(familiar,"rw_cpi_status")));
    payload=JsonObjectSet(payload,"companion_inventory",view);
    return JsonObjectSet(payload,"companion_inventory_protocol",JsonInt(1));
}
void RWCPIAdapter(object familiar,string order,object target=OBJECT_INVALID)
{
    SetLocalString(familiar,"rw_cp_order",order);SetLocalObject(familiar,"rw_cp_order_target",target);
    DeleteLocalInt(familiar,"rw_cp_order_ok");string adapter=GetLocalString(GetModule(),"rw_companion_adapter");if(adapter=="")adapter="rw_cp_order";
    ExecuteScript(adapter,familiar);DeleteLocalString(familiar,"rw_cp_order");DeleteLocalObject(familiar,"rw_cp_order_target");
}
void RWCPICancel(object familiar,string status,int restore=TRUE)
{
    if(!GetIsObjectValid(familiar))return;
    int active=GetLocalString(familiar,"rw_cpi_task")!="";
    DeleteLocalString(familiar,"rw_cpi_task");SetLocalInt(familiar,"rw_cpi_epoch",GetLocalInt(familiar,"rw_cpi_epoch")+1);
    if(status!="")RWCPIStatus(familiar,status);
    if(active && restore && GetLocalInt(familiar,"rw_cpi_moving") && RWCPReady(GetMaster(familiar),familiar)
        && GetLastAssociateCommand(familiar)==GetLocalInt(familiar,"rw_cpi_order"))RWCPIAdapter(familiar,"companion:task_end");
    DeleteLocalInt(familiar,"rw_cpi_moving");
}
int RWCPITaskStart(object owner,object familiar,json work)
{
    object pack=RWCPIPack(owner),target=StringToObject(RWS(work,"target"));
    if(!RWCPIEnabled() || !RWCPIWorkAllowed(owner,work) || !RWCPReady(owner,familiar) || !RWCPIPackOwned(owner,pack)
        || !GetIsObjectValid(target) || GetArea(target)!=GetArea(familiar) || GetDistanceBetween(familiar,target)>RWCPIRadius() || !LineOfSightObject(familiar,target))return FALSE;
    if(!RWCPPreference(owner,"movement") && GetDistanceBetween(familiar,target)>2.5)return FALSE;
    RWCPICancel(familiar,"",TRUE);
    SetLocalObject(familiar,"rw_cpi_owner",owner);SetLocalObject(familiar,"rw_cpi_pack",pack);
    SetLocalInt(familiar,"rw_cpi_type",GetFamiliarCreatureType(owner));SetLocalInt(familiar,"rw_cpi_order",GetLastAssociateCommand(familiar));
    SetLocalInt(familiar,"rw_cpi_task_revision",GetLocalInt(GetModule(),"rw_cpi_revision"));
    SetLocalInt(familiar,"rw_cpi_deadline",GetLocalInt(GetModule(),"rw_tick")+120);
    SetLocalString(familiar,"rw_cpi_task_session",GetLocalString(GetModule(),"rw_session"));
    SetLocalString(familiar,"rw_cpi_task",JsonDump(work));SetLocalInt(familiar,"rw_cpi_phase",0);DeleteLocalInt(familiar,"rw_cpi_trade_done");
    if(RWCPPreference(owner,"movement"))
    {
        SetLocalInt(familiar,"rw_cpi_moving",TRUE);RWCPIAdapter(familiar,"companion:task_move",target);
        if(!GetLocalInt(familiar,"rw_cp_order_ok")){RWCPICancel(familiar,"The familiar movement adapter refused this errand.",TRUE);return FALSE;}
    }
    RWCPIStatus(familiar,"Errand started; no transfer has happened yet.");return TRUE;
}
int RWCPIStart(object owner,object familiar,string id)
{
    json choices=JsonParse(GetLocalString(familiar,"rw_cpi_choices"));int i;
    for(i=0;i<JsonGetLength(choices);i++)
    {json work=JsonArrayGet(choices,i);if(RWS(work,"id")==id)return RWCPITaskStart(owner,familiar,work);}
    return FALSE;
}
int RWCPIExchangeStart(object owner,object familiar)
{
    json work=JsonObject();work=JsonObjectSet(work,"verb",JsonString("exchange"));work=JsonObjectSet(work,"target",JsonString(ObjectToString(owner)));
    work=JsonObjectSet(work,"target_uuid",JsonString(GetObjectUUID(owner)));return RWCPITaskStart(owner,familiar,work);
}
void RWCPIFinish(object familiar,object owner,string result,string emote="")
{
    // Finishing an inspection or failed/cancelled errand changes no inventory.
    // Successful transfers request their save at the actual mutation below.
    RWCPICancel(familiar,result,TRUE);
    if(emote!="" && !GetIsDead(familiar))NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK,emote,familiar);
}
void RWCPITaskTick(object owner,object familiar)
{
    string raw=GetLocalString(familiar,"rw_cpi_task");if(raw=="")return;
    object pack=GetLocalObject(familiar,"rw_cpi_pack");int tick=GetLocalInt(GetModule(),"rw_tick");
    if(!RWCPIEnabled() || !RWCPIWorkAllowed(owner,JsonParse(raw)) || !RWCPReady(owner,familiar) || GetLocalObject(familiar,"rw_cpi_owner")!=owner
        || (GetLocalInt(familiar,"rw_cpi_moving") && !RWCPPreference(owner,"movement"))
        || GetLocalInt(familiar,"rw_cpi_type")!=GetFamiliarCreatureType(owner) || !RWCPIPackOwned(owner,pack)
        || GetLocalString(familiar,"rw_cpi_task_session")!=GetLocalString(GetModule(),"rw_session")
        || GetLocalInt(familiar,"rw_cpi_task_revision")!=GetLocalInt(GetModule(),"rw_cpi_revision")
        || GetLastAssociateCommand(familiar)!=GetLocalInt(familiar,"rw_cpi_order")
        || GetDistanceBetween(owner,familiar)>RWCPIRadius()+2.0)
    {RWCPICancel(familiar,"Errand interrupted; any collected items remain in the owner's satchel.");return;}
    if(tick>=GetLocalInt(familiar,"rw_cpi_deadline"))
    {RWCPIFinish(familiar,owner,"Errand timed out; any collected items remain in the satchel.","*Stops the errand, keeping the belongings packed.*");return;}
    if(GetLocalInt(familiar,"rw_cpi_phase")==3)
    {
        if(GetLocalInt(familiar,"rw_cpi_trade_done"))RWCPICancel(familiar,"",TRUE);
        return;
    }
    json work=JsonParse(raw);string verb=RWS(work,"verb");object target=StringToObject(RWS(work,"target")),item=StringToObject(RWS(work,"item")),offer=StringToObject(RWS(work,"offer"));
    if(!GetIsObjectValid(target) || GetObjectUUID(target)!=RWS(work,"target_uuid") || GetArea(target)!=GetArea(familiar) || GetDistanceBetween(familiar,target)>RWCPIRadius())
    {RWCPIFinish(familiar,owner,"Target is no longer available; collected items remain in the satchel.");return;}
    if(GetDistanceBetween(familiar,target)>2.5)return;
    if(!LineOfSightObject(familiar,target)) {RWCPIFinish(familiar,owner,"The target is blocked.");return;}
    if(verb=="exchange")
    {
        if(!RWCPIWindow(owner,owner,familiar,pack)){RWCPIFinish(familiar,owner,"Exchange window unavailable.");return;}
        SetLocalInt(familiar,"rw_cpi_phase",3);SetLocalInt(familiar,"rw_cpi_deadline",tick+60);RWCPIStatus(familiar,"Owner exchange open; waiting for confirmation.");return;
    }
    int container=verb=="inspect" || verb=="take" || verb=="fetch";
    if(container)
    {
        if(!RWCPIContainer(familiar,target)){RWCPIFinish(familiar,owner,"Container is locked, trapped, scripted or no longer approved.");return;}
        if(!GetIsOpen(target))
        {if(GetLocalInt(familiar,"rw_cpi_phase")==0){SetLocalInt(familiar,"rw_cpi_phase",1);AssignCommand(target,ActionPlayAnimation(ANIMATION_PLACEABLE_OPEN));}return;}
        SetLocalObject(familiar,"rw_cpi_inspected",target);
        if(verb=="inspect"){RWCPIFinish(familiar,owner,"Container inspected; ask again to choose an item.","*Looks carefully through the container.*");return;}
    }
    if(!GetIsObjectValid(item) || GetObjectUUID(item)!=RWS(work,"item_uuid"))
    {RWCPIFinish(familiar,owner,"The selected item is no longer available.");return;}
    int ok=FALSE;
    if(verb=="pickup" || verb=="fetch_ground" || verb=="take" || verb=="fetch")
    {
        if(container)ok=RWCPIMove(item,target,pack,RWCPIMaximum());
        else if(RWCPIGround(familiar,item))ok=NWNX_Item_MoveTo(item,pack);
        if(ok)RWCPISave(owner);
        if(!ok){RWCPIFinish(familiar,owner,"The game refused collection; nothing was copied.");return;}
        if(verb=="fetch" || verb=="fetch_ground")
        {
            // Stack merging destroys object handles. Never guess which stack to deliver.
            if(!GetIsObjectValid(item) || !RWCPISafe(item,pack,RWCPIMaximum()))
            {RWCPIFinish(familiar,owner,"Collected into the satchel; use the exchange window to retrieve the merged stack.","*Packs the collected supplies into the satchel.*");return;}
            work=JsonObjectSet(work,"verb",JsonString("give"));work=JsonObjectSet(work,"target",JsonString(ObjectToString(owner)));work=JsonObjectSet(work,"target_uuid",JsonString(GetObjectUUID(owner)));
            SetLocalString(familiar,"rw_cpi_task",JsonDump(work));SetLocalInt(familiar,"rw_cpi_phase",2);
            RWCPIAdapter(familiar,"companion:task_continue",owner);RWCPIStatus(familiar,"Collected into the satchel; returning to the owner.");return;
        }
        RWCPIFinish(familiar,owner,"Item collected into the satchel.","*Collects the item and packs it away.*");return;
    }
    if(!RWCPIRecipient(familiar,target) || !RWCPISafe(item,pack,RWCPIMaximum()))
    {RWCPIFinish(familiar,owner,"Recipient or item is no longer eligible.");return;}
    if(verb=="give")
    {
        if(GetIsPC(target) && target!=owner)
        {
            if(!RWCPIWindow(target,owner,familiar,pack,item)){RWCPIFinish(familiar,owner,"The recipient could not receive an offer.");return;}
            SetLocalInt(familiar,"rw_cpi_phase",3);SetLocalInt(familiar,"rw_cpi_deadline",tick+60);RWCPIStatus(familiar,"Delivery offered; waiting for the other player's acceptance.");
            NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK,"*Offers the belongings and waits for an answer.*",familiar);return;
        }
        if(!GetIsPC(target) && !RWCPISafe(item,pack,RWI(RWInvPolicy(target),"max_value")))
        {RWCPIFinish(familiar,owner,"The recipient's item rules refused this gift.");return;}
        ok=RWCPIMove(item,pack,target,RWCPIMaximum());
    }
    else if(verb=="swap")
    {
        if(!GetIsObjectValid(offer) || GetObjectUUID(offer)!=RWS(work,"offer_uuid"))
        {RWCPIFinish(familiar,owner,"The offered exchange item is no longer available.");return;}
        ok=RWCPISwap(pack,target,item,offer,RWCPIMaximum(),FALSE);
    }
    if(ok!=0)RWCPISave(owner,target); // Include incomplete compensation.
    RWCPIFinish(familiar,owner,ok>0?"Item transfer completed.":(ok<0?"Exchange partly completed; inspect both inventories before retrying.":"Item transfer rejected by the game."),ok>0?"*Hands over the belongings.*":"");
}
