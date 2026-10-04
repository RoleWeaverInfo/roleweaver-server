// Owner-directed social errands. Movement and speech are validated in the game;
// no companion ever becomes a world-NPC slot or gains the recipient's actions.
#include "rw_cp_items"
#include "rw_address"

float RWCPVRadius() { return IntToFloat(GetLocalInt(GetModule(),"rw_cpv_radius")); }
int RWCPVEnabled() { return GetLocalInt(GetModule(),"rw_cp_enabled") && GetLocalInt(GetModule(),"rw_cpv_enabled"); }
void RWCPVConfig(json cmd)
{
    json p=JsonObjectGet(cmd,"visits"), receivers=JsonObjectGet(p,"receivers");
    int radius=RWI(p,"radius"),i;
    if(radius<3 || radius>40 || JsonGetType(receivers)!=JSON_TYPE_ARRAY || JsonGetLength(receivers)>1000)
    {SetLocalInt(GetModule(),"rw_cpv_enabled",FALSE);return;}
    for(i=0;i<JsonGetLength(receivers);i++)
        if(JsonGetType(JsonArrayGet(receivers,i))!=JSON_TYPE_STRING || !RWValidID(JsonGetString(JsonArrayGet(receivers,i))))
        {SetLocalInt(GetModule(),"rw_cpv_enabled",FALSE);return;}
    SetLocalInt(GetModule(),"rw_cpv_enabled",RWI(p,"enabled")==1);
    SetLocalInt(GetModule(),"rw_cpv_players",RWI(p,"players")==1);
    SetLocalInt(GetModule(),"rw_cpv_radius",radius);
    SetLocalString(GetModule(),"rw_cpv_receivers",JsonDump(receivers));
}
int RWCPVReceiver(object target)
{
    if(GetIsPC(target))return GetLocalInt(GetModule(),"rw_cpv_players");
    string id=GetLocalString(target,"rw_id");
    if(id=="" || RWFind(id)!=target)return FALSE;
    json ids=JsonParse(GetLocalString(GetModule(),"rw_cpv_receivers"));int i;
    for(i=0;i<JsonGetLength(ids);i++)if(JsonGetString(JsonArrayGet(ids,i))==id)return TRUE;
    return FALSE;
}
// A visit never steals another player's selected conversation. Our own short
// reservation is separate, so it can pause idle patrols without blocking itself.
int RWCPVPlayerTalking(object target)
{
    object pc=GetFirstPC();
    while(GetIsObjectValid(pc))
    {if(RWCurrentTalk(pc)==target)return TRUE;pc=GetNextPC();}
    return FALSE;
}
int RWCPVTarget(object familiar,object target)
{
    object visitor=GetLocalObject(target,"rw_cpv_visitor");
    return GetIsObjectValid(target) && target!=familiar && target!=GetMaster(familiar)
        && GetObjectType(target)==OBJECT_TYPE_CREATURE && !GetIsDM(target)
        && !GetIsDMPossessed(target) && !GetIsPossessedFamiliar(target)
        && !GetIsDead(target) && !GetIsInCombat(target) && !IsInConversation(target)
        && !GetIsEnemy(target,familiar) && GetArea(target)==GetArea(familiar)
        && LineOfSightObject(familiar,target) && RWAreaCreatureVisible(familiar,target)
        && RWCPVReceiver(target) && !RWCPVPlayerTalking(target)
        && (visitor==familiar || !RWCompanionVisitHeld(target))
        && (GetIsPC(target) || (GetLocalString(target,"rw_mode")=="auto"
            && GetLocalString(target,"rw_action_status")!="running"
            && GetLocalString(target,"rw_action_status")!="waiting for player"
            && GetLocalString(target,"rw_live_scene")=="" && GetLocalString(target,"rw_persistent_scene")==""));
}
json RWCPVObserve(json e,object owner,object familiar,string instruction)
{
    json choices=JsonArray();int scanned=0;
    object target=GetFirstObjectInArea(GetArea(familiar));
    if(RWCPVEnabled() && RWCPReady(owner,familiar) && RWCPPreference(owner,"movement"))
    while(GetIsObjectValid(target) && scanned<1024 && JsonGetLength(choices)<16)
    {
        if(GetDistanceBetween(familiar,target)<=RWCPVRadius() && RWCPVTarget(familiar,target))
        {
            string label=GetStringLeft(GetName(target),80);
            // Do not teach a familiar every player's name from engine metadata.
            // It may use a name the owner has just supplied in this instruction.
            if(GetIsPC(target) && FindSubString(GetStringLowerCase(instruction),GetStringLowerCase(label))<0)
                label="the traveler "+IntToString(FloatToInt(GetDistanceBetween(familiar,target)))+" metres "+RWVisibleBearing(familiar,target);
            int stay;
            for(stay=0;stay<2;stay++)
            {
                json row=JsonObject();string id="cpvisit:"+IntToString(JsonGetLength(choices));
                row=JsonObjectSet(row,"id",JsonString(id));row=JsonObjectSet(row,"label",JsonString(label));
                row=JsonObjectSet(row,"description",JsonString("On your owner's explicit request, approach "+label+(stay?", ask about the requested topic, stay for up to three short exchanges, then report back.":", ask about the requested topic, then return and report the reply.")));
                row=JsonObjectSet(row,"mode",JsonString(stay?"stay":"return"));
                row=JsonObjectSet(row,"target",JsonString(ObjectToString(target)));
                row=JsonObjectSet(row,"target_uuid",JsonString(GetObjectUUID(target)));
                row=JsonObjectSet(row,"peer_kind",JsonString(GetIsPC(target)?"player":"npc"));
                row=JsonObjectSet(row,"peer",JsonString(GetIsPC(target)?"":GetLocalString(target,"rw_id")));
                row=JsonObjectSet(row,"peer_epoch",JsonInt(GetLocalInt(target,"rw_epoch")));
                choices=JsonArrayInsert(choices,row);
            }
        }
        target=GetNextObjectInArea(GetArea(familiar));scanned++;
    }
    SetLocalString(familiar,"rw_cpv_choices",JsonDump(choices));
    e=JsonObjectSet(e,"companion_visits",choices);
    return JsonObjectSet(e,"companion_visits_protocol",JsonInt(1));
}
json RWCPVEvent(string kind,object familiar)
{
    object owner=GetMaster(familiar),target=GetLocalObject(familiar,"rw_cpv_target");
    json e=RWCPEvent(kind,owner,familiar);
    e=JsonObjectSet(e,"visit",JsonString(GetLocalString(familiar,"rw_cpv_id")));
    e=JsonObjectSet(e,"generation",JsonString(GetLocalString(familiar,"rw_cpv_generation")));
    e=JsonObjectSet(e,"phase",JsonString(GetLocalString(familiar,"rw_cpv_phase")));
    e=JsonObjectSet(e,"step",JsonInt(GetLocalInt(familiar,"rw_cpv_step")));
    e=JsonObjectSet(e,"target_uuid",JsonString(GetLocalString(familiar,"rw_cpv_target_uuid")));
    return JsonObjectSet(e,"reason",JsonString(GetLocalString(familiar,"rw_cpv_reason")));
}
void RWCPVRelease(object familiar)
{
    object target=GetLocalObject(familiar,"rw_cpv_target");
    if(GetLocalObject(target,"rw_cpv_visitor")==familiar)DeleteLocalObject(target,"rw_cpv_visitor");
}
void RWCPVCancel(object familiar,string reason="",int restore=TRUE)
{
    if(!GetIsObjectValid(familiar) || GetLocalString(familiar,"rw_cpv_id")=="")return;
    RWEmit(RWCPVEvent("companion_visit_end",familiar));
    RWCPVRelease(familiar);DeleteLocalString(familiar,"rw_cpv_id");
    SetLocalString(familiar,"rw_cpv_status",reason);
    object owner=GetMaster(familiar);
    // Restoring the previous stock mode does not require loaded AI preferences.
    // A new native command, combat or possession always takes precedence.
    if(restore && GetIsPC(owner) && GetLocalObject(familiar,"rw_cpv_owner")==owner
        && GetAssociate(ASSOCIATE_TYPE_FAMILIAR,owner)==familiar && !GetIsDead(familiar)
        && !GetIsInCombat(familiar) && !GetIsInCombat(owner) && !GetIsDMPossessed(familiar)
        && !GetIsPossessedFamiliar(familiar) && !IsInConversation(familiar)
        && GetLastAssociateCommand(familiar)==GetLocalInt(familiar,"rw_cpv_order"))
        RWCPIAdapter(familiar,"companion:task_end");
}
void RWCPVPhase(object familiar,string phase)
{
    SetLocalString(familiar,"rw_cpv_phase",phase);
    SetLocalInt(familiar,"rw_cpv_step",GetLocalInt(familiar,"rw_cpv_step")+1);
    SetLocalInt(familiar,"rw_cpv_until",GetLocalInt(GetModule(),"rw_tick")+45);
}
void RWCPVReturn(object familiar,string reason="")
{
    RWCPVRelease(familiar);SetLocalString(familiar,"rw_cpv_reason",reason);
    RWCPVPhase(familiar,"return");SetLocalString(familiar,"rw_cpv_status","Returning to report what was actually said.");
    RWCPIAdapter(familiar,"companion:task_continue",GetMaster(familiar));
}
int RWCPVStart(object owner,object familiar,string id,string visit)
{
    if(!RWCPVEnabled() || !RWCPReady(owner,familiar) || !RWCPPreference(owner,"movement") || GetStringLength(visit)!=24)return FALSE;
    json choices=JsonParse(GetLocalString(familiar,"rw_cpv_choices")),row=JSON_NULL;int i;
    for(i=0;i<JsonGetLength(choices);i++)if(RWS(JsonArrayGet(choices,i),"id")==id)row=JsonArrayGet(choices,i);
    object target=StringToObject(RWS(row,"target"));
    if(!RWCPVTarget(familiar,target) || GetDistanceBetween(familiar,target)>RWCPVRadius()
        || GetObjectUUID(target)!=RWS(row,"target_uuid") || GetLocalInt(target,"rw_epoch")!=RWI(row,"peer_epoch"))return FALSE;
    RWCPVCancel(familiar,"Previous visit cancelled.");RWCPICancel(familiar,"Inventory errand cancelled for a visit.",TRUE);
    SetLocalString(familiar,"rw_cpv_id",visit);SetLocalObject(familiar,"rw_cpv_owner",owner);
    SetLocalString(familiar,"rw_cpv_owner_key",RWCPOwnerKey(owner));
    SetLocalString(familiar,"rw_cpv_session",GetLocalString(GetModule(),"rw_session"));
    SetLocalString(familiar,"rw_cpv_generation",GetLocalString(GetModule(),"rw_cpp_generation"));
    SetLocalObject(familiar,"rw_cpv_target",target);SetLocalString(familiar,"rw_cpv_target_uuid",GetObjectUUID(target));
    SetLocalInt(familiar,"rw_cpv_peer_epoch",GetLocalInt(target,"rw_epoch"));
    SetLocalInt(familiar,"rw_cpv_type",GetFamiliarCreatureType(owner));
    SetLocalString(familiar,"rw_cpv_mode",RWS(row,"mode"));
    SetLocalInt(familiar,"rw_cpv_turns",0);SetLocalInt(familiar,"rw_cpv_step",0);DeleteLocalString(familiar,"rw_cpv_reason");
    SetLocalLocation(familiar,"rw_cpv_origin",GetLocation(familiar));
    SetLocalInt(familiar,"rw_cpv_deadline",GetLocalInt(GetModule(),"rw_tick")+180);
    SetLocalInt(familiar,"rw_cpv_order",GetLastAssociateCommand(familiar));
    RWCPIAdapter(familiar,"companion:task_move",target);
    if(!GetLocalInt(familiar,"rw_cp_order_ok")){RWCPVCancel(familiar,"Visit movement was refused.");return FALSE;}
    RWCPVPhase(familiar,"travel");SetLocalString(familiar,"rw_cpv_status","Walking to the requested conversation partner.");return TRUE;
}
int RWCPVValid(object familiar)
{
    object owner=GetMaster(familiar);
    return RWCPVEnabled() && RWCPReady(owner,familiar) && RWCPPreference(owner,"movement")
        && GetLocalObject(familiar,"rw_cpv_owner")==owner && GetLocalString(familiar,"rw_cpv_owner_key")==RWCPOwnerKey(owner)
        && GetLocalInt(familiar,"rw_cpv_type")==GetFamiliarCreatureType(owner)
        && GetLocalString(familiar,"rw_cpv_session")==GetLocalString(GetModule(),"rw_session")
        && GetLocalString(familiar,"rw_cpv_generation")==GetLocalString(GetModule(),"rw_cpp_generation")
        && GetLastAssociateCommand(familiar)==GetLocalInt(familiar,"rw_cpv_order")
        && GetDistanceBetween(owner,familiar)<=RWCPVRadius()+2.0;
}
void RWCPVTick(object familiar)
{
    if(GetLocalString(familiar,"rw_cpv_id")=="")return;
    object owner=GetMaster(familiar),target=GetLocalObject(familiar,"rw_cpv_target");
    int tick=GetLocalInt(GetModule(),"rw_tick");string phase=GetLocalString(familiar,"rw_cpv_phase");
    if(!RWCPVValid(familiar))
    {RWCPVCancel(familiar,"Visit interrupted by control, permissions, combat or separation.");return;}
    if(phase=="return" || phase=="report")
    {
        if(tick>GetLocalInt(familiar,"rw_cpv_until"))
        {RWCPVCancel(familiar,"Could not return and report in time.");SendMessageToPC(owner,"Your familiar's visit ended before it could report back.");return;}
        if(phase=="return" && GetDistanceBetween(owner,familiar)<=3.0 && LineOfSightObject(owner,familiar))RWCPVPhase(familiar,"report");
    }
    else if(tick>GetLocalInt(familiar,"rw_cpv_deadline") || tick>GetLocalInt(familiar,"rw_cpv_until"))RWCPVReturn(familiar,phase=="travel"?"unreachable":"no_reply");
    else if(!RWCPVTarget(familiar,target) || GetObjectUUID(target)!=GetLocalString(familiar,"rw_cpv_target_uuid")
        || GetLocalInt(target,"rw_epoch")!=GetLocalInt(familiar,"rw_cpv_peer_epoch")
        || GetDistanceBetweenLocations(GetLocalLocation(familiar,"rw_cpv_origin"),GetLocation(target))>RWCPVRadius())RWCPVReturn(familiar,"unavailable");
    else if(phase=="travel" && GetDistanceBetween(familiar,target)<=3.0)
    {
        SetLocalObject(target,"rw_cpv_visitor",familiar);RWCPVPhase(familiar,"ask");
        SetLocalString(familiar,"rw_cpv_status","Asking about the owner's requested topic.");
        if(GetIsPC(target))SendMessageToPC(target,GetName(familiar)+" has a question. Reply in nearby Talk using its name, or /rw companion reply <answer>. Your answer will be reported to its owner. /rw companion decline ends the visit.");
    }
    else if(phase!="travel" && GetDistanceBetween(familiar,target)>4.0)RWCPVReturn(familiar,"unavailable");
    RWEmit(RWCPVEvent("companion_visit_state",familiar));
}
void RWCPVAnswered(object familiar)
{
    int turns=GetLocalInt(familiar,"rw_cpv_turns")+1;SetLocalInt(familiar,"rw_cpv_turns",turns);
    if(GetLocalString(familiar,"rw_cpv_mode")=="stay" && turns<3)RWCPVPhase(familiar,"ask");
    else RWCPVReturn(familiar);
}
void RWCPVReply(json cmd)
{
    object familiar=StringToObject(RWS(cmd,"object")),owner=GetMaster(familiar),target=GetLocalObject(familiar,"rw_cpv_target");
    if(!RWCPVValid(familiar) || RWS(cmd,"visit")=="" || RWS(cmd,"visit")!=GetLocalString(familiar,"rw_cpv_id")
        || RWS(cmd,"owner")!=RWCPOwnerKey(owner) || RWS(cmd,"generation")!=GetLocalString(familiar,"rw_cpv_generation")
        || RWI(cmd,"step")!=GetLocalInt(familiar,"rw_cpv_step") || RWS(cmd,"request")==GetLocalString(familiar,"rw_cpv_ack"))return;
    string verb=RWS(cmd,"action"),phase=GetLocalString(familiar,"rw_cpv_phase"),text=RWS(cmd,"text");
    int ok=FALSE;
    if(verb=="return" && phase!="return" && phase!="report")
    {SetLocalString(familiar,"rw_cpv_ack",RWS(cmd,"request"));RWCPVReturn(familiar,"no_reply");ok=TRUE;}
    else if(verb==phase && (phase=="ask" || phase=="answer" || phase=="report") && text!="" && GetStringLength(text)<=900)
    {
        int close=phase=="report" ? GetDistanceBetween(familiar,owner)<=3.0 && LineOfSightObject(familiar,owner)
            : RWCPVTarget(familiar,target) && GetObjectUUID(target)==GetLocalString(familiar,"rw_cpv_target_uuid")
                && GetLocalInt(target,"rw_epoch")==GetLocalInt(familiar,"rw_cpv_peer_epoch") && GetDistanceBetween(familiar,target)<=4.0;
        if(close && (phase!="answer" || !GetIsPC(target)))
        {SetLocalString(familiar,"rw_cpv_ack",RWS(cmd,"request"));ok=RWPublicSpeak(text,phase=="answer"?target:familiar);}
    }
    json ack=cmd;ack=JsonObjectSet(ack,"kind",JsonString("companion_visit_ack"));ack=JsonObjectSet(ack,"ok",JsonInt(ok));RWEmit(ack);
    if(!ok){RWCPVReturn(familiar,"no_reply");return;}
    if(verb=="ask")RWCPVPhase(familiar,GetIsPC(target)?"wait_player":"answer");
    else if(verb=="answer")RWCPVAnswered(familiar);
    else if(verb=="report")RWCPVCancel(familiar,"Visit completed; report delivered.");
}
// Capture only the invited player's explicit response, never ambient chat/tells.
int RWCPVPlayerChat(object player,string text)
{
    if(GetLocalInt(player,"rw_cpv_echo"))return TRUE;
    object familiar=GetLocalObject(player,"rw_cpv_visitor");
    if(!GetIsObjectValid(familiar) || GetLocalObject(familiar,"rw_cpv_target")!=player || !RWCPVValid(familiar)
        || !GetIsPC(player) || !RWCPVTarget(familiar,player) || GetDistanceBetween(familiar,player)>4.0)return FALSE;
    string lower=RWTrimAddress(text);int slash=GetStringLeft(lower,14)=="/rw companion ";
    if(lower=="/rw companion decline")
    {RWCPVReturn(familiar,"declined");SendMessageToPC(player,"You declined the familiar's visit.");return TRUE;}
    if(GetLocalString(familiar,"rw_cpv_phase")!="wait_player")return FALSE;
    string body=text;
    if(GetStringLeft(lower,20)=="/rw companion reply ")body=GetSubString(text,20,GetStringLength(text));
    else
    {
        if(slash || GetStringLeft(lower,1)=="/" || GetStringLeft(lower,2)=="(("
            || !RWNameMatch(RWAddress(text),lower,familiar))return FALSE;
    }
    if(body=="" || GetStringLength(body)>600){SendMessageToPC(player,"Please keep the reply under 600 characters.");return TRUE;}
    // The reply helper is public speech too; the normal chat router hides only
    // its slash command, and never treats this answer as an owner instruction.
    if(slash)
    {
        SetLocalInt(player,"rw_cpv_echo",TRUE);
        int spoken=RWPublicSpeak(body,player);
        DeleteLocalInt(player,"rw_cpv_echo");if(!spoken)return TRUE;
    }
    json e=RWCPVEvent("companion_visit_player",familiar);e=JsonObjectSet(e,"text",JsonString(body));RWEmit(e);
    string answer=GetStringLowerCase(body);
    if(FindSubString(answer,"no thanks")>=0 || FindSubString(answer,"leave me alone")>=0
        || FindSubString(answer,"go away")>=0 || FindSubString(answer,"don't want to talk")>=0)
    {RWCPVReturn(familiar,"declined");return TRUE;}
    RWCPVAnswered(familiar);return TRUE;
}
