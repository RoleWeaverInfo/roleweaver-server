// Familiar cargo uses one real, owner-carried bag per world and familiar type.
// There is no serialized item mirror and nothing is recreated on resummoning.
#include "rw_cp_prefs"
#include "rw_inventory"

int RWCPIEnabled()
{return GetLocalInt(GetModule(),"rw_cp_enabled") && GetLocalInt(GetModule(),"rw_cpi_enabled") && NWNX_Core_PluginExists("NWNX_Item");}
int RWCPIMaximum() {return GetLocalInt(GetModule(),"rw_cpi_max_value");}
float RWCPIRadius() {return IntToFloat(GetLocalInt(GetModule(),"rw_cpi_radius"));}
void RWCPIConfig(json cmd)
{
    json p=JsonObjectGet(cmd,"inventory");int radius=RWI(p,"radius"),maximum=RWI(p,"max_value");
    json tags=JsonObjectGet(p,"containers");int i;
    if(radius<3 || radius>40 || maximum<0 || maximum>100000 || JsonGetType(tags)!=JSON_TYPE_ARRAY || JsonGetLength(tags)>30)
    {SetLocalInt(GetModule(),"rw_cpi_enabled",FALSE);return;}
    for(i=0;i<JsonGetLength(tags);i++)
        if(JsonGetType(JsonArrayGet(tags,i))!=JSON_TYPE_STRING || GetStringLength(JsonGetString(JsonArrayGet(tags,i)))<1 || GetStringLength(JsonGetString(JsonArrayGet(tags,i)))>128)
        {SetLocalInt(GetModule(),"rw_cpi_enabled",FALSE);return;}
    string policy=JsonDump(p);
    if(policy!=GetLocalString(GetModule(),"rw_cpi_policy"))
        SetLocalInt(GetModule(),"rw_cpi_revision",GetLocalInt(GetModule(),"rw_cpi_revision")+1);
    SetLocalString(GetModule(),"rw_cpi_policy",policy);
    SetLocalString(GetModule(),"rw_cpi_containers",JsonDump(tags));
    SetLocalInt(GetModule(),"rw_cpi_radius",radius);SetLocalInt(GetModule(),"rw_cpi_max_value",maximum);
    SetLocalInt(GetModule(),"rw_cpi_enabled",RWI(p,"enabled")==1);
}

// GetItemPossessor returns a bag item's *creature* owner on NWN, not its bag.
// Creature iteration also includes bag contents. A deposit must additionally
// exclude items already inside the destination satchel (see RWCPIIncoming).
int RWCPIContains(object holder,object item)
{
    if(!GetIsObjectValid(holder) || !GetIsObjectValid(item))return FALSE;
    object next=GetFirstItemInInventory(holder);int count=0;
    while(GetIsObjectValid(next) && count<2048)
    {if(next==item)return TRUE;next=GetNextItemInInventory(holder);count++;}
    return FALSE;
}
int RWCPISafe(object item,object holder,int maximum)
{
    return RWCPIContains(holder,item) && RWInvSafe(item,GetItemPossessor(item),maximum);
}
int RWCPIIncoming(object item,object holder,object pack,int maximum)
{
    return RWCPISafe(item,holder,maximum) && !RWCPIContains(pack,item);
}
int RWCPIPackOwned(object owner,object pack)
{
    return GetIsObjectValid(pack) && GetHasInventory(pack) && GetObjectType(pack)==OBJECT_TYPE_ITEM
        && GetLocalInt(pack,"rw_cp_satchel")==1 && GetLocalString(pack,"rw_cp_world")==RWWorld()
        && GetLocalString(pack,"rw_cp_owner")==RWCPOwnerKey(owner)
        && GetItemPossessor(pack)==owner && RWCPIContains(owner,pack);
}
object RWCPIPack(object owner,int create=FALSE)
{
    int type=GetFamiliarCreatureType(owner),matches=0,scanned=0;
    object item=GetFirstItemInInventory(owner),found=OBJECT_INVALID;
    while(GetIsObjectValid(item) && scanned<2048)
    {
        if(RWCPIPackOwned(owner,item) && GetLocalInt(item,"rw_cp_type")==type)
        {found=item;matches++;}
        item=GetNextItemInInventory(owner);scanned++;
    }
    // Ambiguous/oversized inventories require manual attention, never a new copy.
    if(matches>1 || GetIsObjectValid(item))return OBJECT_INVALID;
    if(matches==1 || !create || !GetIsPC(owner) || !RWCPIEnabled())return found;
    string resref=GetLocalString(GetModule(),"rw_cp_pack_resref");
    if(resref=="")resref="nw_it_contain001";
    object pack=CreateItemOnObject(resref,owner,1,"rw_cp_satchel");
    if(!GetIsObjectValid(pack) || !GetHasInventory(pack) || GetIsObjectValid(GetFirstItemInInventory(pack)))
    {if(GetIsObjectValid(pack))DestroyObject(pack);return OBJECT_INVALID;}
    // This is an ordinary storage bag, with no free magic-item properties.
    itemproperty ip=GetFirstItemProperty(pack);int properties=0;
    while(GetIsItemPropertyValid(ip) && properties<64)
    {RemoveItemProperty(pack,ip);ip=GetFirstItemProperty(pack);properties++;}
    if(GetIsItemPropertyValid(ip)){DestroyObject(pack);return OBJECT_INVALID;}
    SetName(pack,"Familiar Satchel");SetIdentified(pack,TRUE);SetDroppableFlag(pack,FALSE);SetPlotFlag(pack,TRUE);
    SetLocalInt(pack,"rw_cp_satchel",1);SetLocalInt(pack,"rw_cp_type",type);
    SetLocalString(pack,"rw_cp_world",RWWorld());SetLocalString(pack,"rw_cp_owner",RWCPOwnerKey(owner));
    ExportSingleCharacter(owner);
    return pack;
}
int RWCPIGround(object familiar,object item)
{
    return GetIsObjectValid(item) && GetObjectType(item)==OBJECT_TYPE_ITEM
        && !GetIsObjectValid(GetItemPossessor(item)) && !GetLocalInt(item,"rw_no_companion")
        && RWInvSafe(item,OBJECT_INVALID,RWCPIMaximum())
        && GetArea(item)==GetArea(familiar) && GetDistanceBetween(familiar,item)<=RWCPIRadius()
        && LineOfSightObject(familiar,item);
}
int RWCPIContainer(object familiar,object box)
{
    if(!GetIsObjectValid(box) || GetObjectType(box)!=OBJECT_TYPE_PLACEABLE || !GetHasInventory(box)
        || GetLocalInt(box,"rw_no_companion") || !GetUseableFlag(box) || GetLocked(box) || GetIsTrapped(box)
        || GetArea(box)!=GetArea(familiar) || !LineOfSightObject(familiar,box) || GetDistanceBetween(familiar,box)>RWCPIRadius()
        || GetEventScript(box,EVENT_SCRIPT_PLACEABLE_ON_OPEN)!="" || GetEventScript(box,EVENT_SCRIPT_PLACEABLE_ON_USED)!="")return FALSE;
    json tags=JsonParse(GetLocalString(GetModule(),"rw_cpi_containers"));int i;
    for(i=0;i<JsonGetLength(tags);i++)if(JsonGetString(JsonArrayGet(tags,i))==GetTag(box))return TRUE;
    return FALSE;
}
int RWCPIRecipient(object familiar,object who)
{
    return GetIsObjectValid(who) && who!=familiar && !GetIsDM(who) && !GetIsDMPossessed(who)
        && !GetIsPossessedFamiliar(who) && !GetIsDead(who) && !GetIsInCombat(who)
        && GetArea(who)==GetArea(familiar) && !GetIsEnemy(who,familiar)
        && GetDistanceBetween(familiar,who)<=RWCPIRadius() && LineOfSightObject(familiar,who)
        && (GetIsPC(who) || (GetLocalString(who,"rw_id")!="" && RWInvReady(who) && RWInvFlag(who,"receive")));
}
void RWCPISave(object owner,object recipient=OBJECT_INVALID)
{
    if(GetIsPC(owner))ExportSingleCharacter(owner);
    if(recipient!=owner && GetIsPC(recipient))ExportSingleCharacter(recipient);
}
// Only successful native moves count. No creation, copying, or retries.
int RWCPIMove(object item,object source,object target,int maximum)
{
    if(!RWCPISafe(item,source,maximum) || source==target
        || (GetObjectType(target)==OBJECT_TYPE_ITEM && RWCPIContains(target,item)))return FALSE;
    return NWNX_Item_MoveTo(item,target);
}
int RWCPISwapOK(object pack,object recipient,object give,object offer,int maximum,int ownerExchange)
{
    if(give==offer || !RWCPISafe(give,pack,maximum) || !RWCPIIncoming(offer,recipient,pack,maximum)
        || GetItemStackSize(give)!=1 || GetItemStackSize(offer)!=1
        || StringToInt(Get2DAString("baseitems","Stacking",GetBaseItemType(give)))>1
        || StringToInt(Get2DAString("baseitems","Stacking",GetBaseItemType(offer)))>1)return FALSE;
    if(ownerExchange)return TRUE;
    return !GetIsPC(recipient) && RWInvFlag(recipient,"exchange") && RWInvFlag(recipient,"receive")
        && RWCPISafe(give,pack,RWI(RWInvPolicy(recipient),"max_value"))
        && RWCPISafe(offer,recipient,RWI(RWInvPolicy(recipient),"max_value"))
        && GetGoldPieceValue(offer)>=GetGoldPieceValue(give)
        && GetGoldPieceValue(give)*100>=GetGoldPieceValue(offer)*RWI(RWInvPolicy(recipient),"barter_percent");
}
int RWCPISwap(object pack,object recipient,object give,object offer,int maximum,int ownerExchange)
{
    if(!RWCPISwapOK(pack,recipient,give,offer,maximum,ownerExchange))return FALSE;
    if(!NWNX_Item_MoveTo(offer,pack))return FALSE;
    if(!RWCPISafe(give,pack,maximum) || !NWNX_Item_MoveTo(give,recipient))
    {if(!NWNX_Item_MoveTo(offer,recipient))return -1;return FALSE;}
    return TRUE;
}
void RWCPIStatus(object familiar,string status)
{SetLocalString(familiar,"rw_cpi_status",status);}
