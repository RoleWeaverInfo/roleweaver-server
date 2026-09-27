// Included by rw_actions. Never resolve a model-provided engine object ID.
int RWNearbyKind(string kind)
{ return kind=="approach" || kind=="open_door" || kind=="close_door" || kind=="sit" || kind=="visit"; }

int RWNearbyVisible(object npc,object target)
{
    return GetIsObjectValid(target) && target!=npc && !GetIsPC(target) && !GetIsDM(target)
        && !GetIsDMPossessed(target) && GetArea(target)==GetArea(npc)
        && LineOfSightObject(npc,target)
        && (GetObjectType(target)!=OBJECT_TYPE_CREATURE || (!GetIsDead(target) && GetObjectSeen(target,npc)));
}

int RWNearbyStart(object npc,json cmd)
{
    string kind=RWS(cmd,"action"), ref=RWS(cmd,"target");
    int radius=RWI(cmd,"radius"), tick=GetLocalInt(GetModule(),"rw_tick");
    if(radius<2 || radius>12 || GetStringLength(ref)>11 || GetStringLeft(ref,1)!="v"
        || tick-GetLocalInt(npc,"rw_perception_tick")>3)return FALSE;
    object target=GetLocalObject(npc,"rw_visible_"+ref);
    if(!RWNearbyVisible(npc,target) || GetDistanceBetween(npc,target)>IntToFloat(radius))return FALSE;
    if(kind=="open_door" || kind=="close_door")
    {
        // Do not unlock, bash, disarm or enter transitions. Door scripts still run normally.
        if(GetObjectType(target)!=OBJECT_TYPE_DOOR || !GetUseableFlag(target)
            || GetLocked(target) || GetIsObjectValid(GetTransitionTarget(target)))return FALSE;
    }
    if(kind=="sit")
    {
        if(GetObjectType(target)!=OBJECT_TYPE_PLACEABLE || GetHasInventory(target)
            || RWS(cmd,"seat_tag")=="" || GetTag(target)!=RWS(cmd,"seat_tag")
            || GetIsObjectValid(GetSittingCreature(target)))return FALSE;
    }
    if(kind=="visit")
    {
        if(GetLocalString(target,"rw_id")=="" || GetLocalString(target,"rw_mode")!="auto"
            || GetIsInCombat(target) || RWHasConversation(target)
            || GetLocalString(target,"rw_action_status")=="running")return FALSE;
        // The player asked us to speak to someone else: release their current focus.
        object listener=StringToObject(RWS(cmd,"listener"));
        if(GetIsObjectValid(listener) && RWCurrentTalk(listener)==npc)RWEndTalk(listener);
        if(RWHasConversation(npc))return FALSE;
    }
    SetLocalObject(npc,"rw_nearby_target",target);
    SetLocalLocation(npc,"rw_nearby_origin",GetLocation(npc));
    SetLocalInt(npc,"rw_nearby_radius",radius);
    SetLocalInt(npc,"rw_nearby_phase",0);
    SetLocalInt(npc,"rw_nearby_peer_epoch",GetLocalInt(target,"rw_epoch"));
    return TRUE;
}

// Return an empty string while pending. Verify effects instead of assuming success.
string RWNearbyTick(object npc)
{
    string kind=GetLocalString(npc,"rw_action_kind");
    object target=GetLocalObject(npc,"rw_nearby_target");
    int tick=GetLocalInt(GetModule(),"rw_tick");
    location origin=GetLocalLocation(npc,"rw_nearby_origin");
    float radius=IntToFloat(GetLocalInt(npc,"rw_nearby_radius"));
    if(!RWNearbyVisible(npc,target))return "target unavailable";
    if(GetArea(npc)!=GetAreaFromLocation(origin)
        || GetDistanceBetweenLocations(origin,GetLocation(npc))>radius+1.0
        || GetDistanceBetweenLocations(origin,GetLocation(target))>radius)return "movement limit reached";
    if(kind=="visit" && (RWHasConversation(npc) || RWHasConversation(target)
        || GetIsInCombat(target) || GetLocalString(target,"rw_mode")!="auto"
        || GetLocalInt(target,"rw_epoch")!=GetLocalInt(npc,"rw_nearby_peer_epoch")))return "conversation interrupted";
    if(kind=="sit" && GetSittingCreature(target)==npc)return "completed";
    if((kind=="open_door" && GetIsOpen(target)) || (kind=="close_door" && !GetIsOpen(target)))return "completed";
    if(tick>=GetLocalInt(npc,"rw_action_deadline"))return "timed out";
    if(GetDistanceBetween(npc,target)>2.0)return "";
    if(kind=="approach" || kind=="visit")return "completed";
    if(GetLocalInt(npc,"rw_nearby_phase"))return "";
    if((kind=="open_door" || kind=="close_door") && GetLocked(target))return "door unavailable";
    if(kind=="sit" && GetIsObjectValid(GetSittingCreature(target)))return "seat occupied";
    SetLocalInt(npc,"rw_nearby_phase",1);
    AssignCommand(npc,ClearAllActions(TRUE));
    if(kind=="open_door")AssignCommand(npc,ActionOpenDoor(target));
    else if(kind=="close_door")AssignCommand(npc,ActionCloseDoor(target));
    else if(kind=="sit")AssignCommand(npc,ActionSit(target));
    return "";
}
