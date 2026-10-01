// Deterministic, single-target warning trigger. The LLM never chooses an attack target.
#include "rw_inc"
#include "nwnx_chat"
// Persistent authority is assigned only by a validated arm command. Never let
// a persistent scene claim a temporary live-scene creature.
int RWEncounterOwner(object npc,json cmd)
{
    string live=RWS(cmd,"live_owner"), persistent=RWS(cmd,"persistent_owner");
    if(live!="")return persistent=="" && live==GetLocalString(npc,"rw_live_owner")
        && RWS(cmd,"encounter")==GetLocalString(npc,"rw_live_scene");
    return persistent!="" && GetLocalString(npc,"rw_live_owner")==""
        && persistent==GetLocalString(npc,"rw_persistent_owner")
        && RWS(cmd,"encounter")==GetLocalString(npc,"rw_persistent_scene");
}
void RWEncounterEvent(object leader, string status)
{
    SetLocalString(leader,"rw_enc_status",status);
    json e=RWBase("encounter_event",leader);
    e=JsonObjectSet(e,"encounter",JsonString(GetLocalString(leader,"rw_enc_id")));
    e=JsonObjectSet(e,"token",JsonString(GetLocalString(leader,"rw_enc_token")));
    e=JsonObjectSet(e,"status",JsonString(status)); RWEmit(e);
}
int RWEncounterPlayer(object pc, object area)
{
    return GetIsObjectValid(pc) && GetIsPC(pc) && !GetIsDM(pc) && !GetIsDMPossessed(pc)
        && !GetIsDead(pc) && GetArea(pc)==area;
}
int RWEncounterCast(object leader)
{
    json cast=JsonParse(GetLocalString(leader,"rw_enc_cast"));
    int i; int count=JsonGetLength(cast);
    if(count<1 || count>8) return FALSE;
    for(i=0;i<count;i++)
    {
        json row=JsonArrayGet(cast,i); object npc=RWFind(RWS(row,"npc"));
        if(!GetIsObjectValid(npc) || GetIsPC(npc) || GetIsDMPossessed(npc) || GetIsDead(npc)
            || GetIsInCombat(npc) || GetLocalString(npc,"rw_mode")!="auto"
            || GetLocalInt(npc,"rw_epoch")!=RWI(row,"epoch")
            || GetArea(npc)!=GetAreaFromLocation(GetLocalLocation(leader,"rw_enc_anchor"))
            || GetDistanceBetweenLocations(GetLocation(npc),GetLocalLocation(leader,"rw_enc_anchor"))>30.0) return FALSE;
    }
    return TRUE;
}
// Each actor owns its combat monitor, so a dead spokesperson cannot strand survivors.
void RWCombatEvent(object npc,string status)
{
    json e=RWBase("encounter_event",npc);
    e=JsonObjectSet(e,"encounter",JsonString(GetLocalString(npc,"rw_combat_id")));
    e=JsonObjectSet(e,"token",JsonString(GetLocalString(npc,"rw_combat_token")));
    e=JsonObjectSet(e,"status",JsonString(status));RWEmit(e);
}
void RWCombatMove(location home)
{
    ClearAllActions(TRUE);
    ActionMoveToLocation(home,TRUE);
    SetCommandable(FALSE);
}
void RWCombatReturn(object npc,string reason)
{
    int tick=GetLocalInt(GetModule(),"rw_tick");
    SetLocalString(npc,"rw_combat_phase","returning");
    SetLocalInt(npc,"rw_combat_deadline",tick+30);
    SetLocalInt(npc,"rw_combat_move_at",0);
    SetLocalInt(npc,"rw_combat_commandable",GetCommandable(npc));
    SetLocalInt(npc,"rw_combat_locked",TRUE);
    SetLocalString(npc,"rw_action_status","interrupted");
    if(GetLocalString(npc,"rw_combat_reason")!=reason)RWCombatEvent(npc,reason);
    SetLocalString(npc,"rw_combat_reason",reason);
}
void RWCombatTick(object npc)
{
    if(!GetLocalInt(npc,"rw_combat_active"))return;
    if(GetIsPC(npc) || GetIsDead(npc) || GetIsDMPossessed(npc)
        || GetLocalString(npc,"rw_mode")!="auto"
        || GetLocalInt(npc,"rw_epoch")!=GetLocalInt(npc,"rw_combat_epoch"))
    {RWCombatRelease(npc);return;}
    int tick=GetLocalInt(GetModule(),"rw_tick");
    location home=GetLocalLocation(npc,"rw_combat_home");
    location anchor=GetLocalLocation(npc,"rw_combat_anchor");
    object target=GetLocalObject(npc,"rw_combat_target");
    string phase=GetLocalString(npc,"rw_combat_phase");
    if(GetArea(npc)!=GetAreaFromLocation(home))
    {RWCombatRelease(npc);RWCombatEvent(npc,"return_failed");return;}
    if(phase=="fighting")
    {
        int hp=GetLocalInt(npc,"rw_combat_hp"), leash=GetLocalInt(npc,"rw_combat_leash");
        if(hp>0 && GetCurrentHitPoints(npc)*100<=GetMaxHitPoints(npc)*hp)
            RWCombatReturn(npc,"low_health");
        else if((!GetLocalInt(npc,"rw_combat_target_npc") && !RWEncounterPlayer(target,GetAreaFromLocation(anchor)))
            || (GetLocalInt(npc,"rw_combat_target_npc") && (!GetIsObjectValid(target) || GetIsDead(target) || GetIsPC(target) || GetArea(target)!=GetAreaFromLocation(anchor))))
            RWCombatReturn(npc,"target_gone");
        else if(leash>0 && (GetDistanceBetweenLocations(GetLocation(target),anchor)>IntToFloat(leash)
            || GetDistanceBetweenLocations(GetLocation(npc),anchor)>IntToFloat(leash)))
            RWCombatReturn(npc,"pursuit_limit");
    }
    // Once withdrawn, never reissue the original attack. If native AI resumes combat
    // or moves away, redirect it home again while this monitor owns the actor.
    else if(phase=="withdrawn" && (GetIsInCombat(npc) || GetDistanceBetweenLocations(GetLocation(npc),home)>2.0))
        RWCombatReturn(npc,"pursuit_limit");
    if(GetLocalString(npc,"rw_combat_phase")!="returning")return;
    if(tick>=GetLocalInt(npc,"rw_combat_deadline"))
    {
        RWCombatRelease(npc);
        AssignCommand(npc,ClearAllActions(TRUE));
        RWCombatEvent(npc,"return_failed");return;
    }
    if(GetDistanceBetweenLocations(GetLocation(npc),home)<=1.5)
    {
        SetCommandable(GetLocalInt(npc,"rw_combat_commandable"),npc);
        DeleteLocalInt(npc,"rw_combat_locked");
        AssignCommand(npc,ClearAllActions(TRUE));
        SetLocalString(npc,"rw_combat_phase","withdrawn");
        if(!GetLocalInt(npc,"rw_combat_return_reported"))RWCombatEvent(npc,"returned");
        SetLocalInt(npc,"rw_combat_return_reported",TRUE);return;
    }
    if(tick>=GetLocalInt(npc,"rw_combat_move_at"))
    {
        SetLocalInt(npc,"rw_combat_move_at",tick+3);
        SetCommandable(TRUE,npc);
        AssignCommand(npc,RWCombatMove(home));
    }
}
// Positions come from fresh game-reported DM captures, scoped to this area object.
object RWEncounterPointArea(json p)
{
    object a=StringToObject(RWS(p,"area_object"));
    object candidate=GetFirstArea(); int found=FALSE;
    while(GetIsObjectValid(candidate))
    {if(candidate==a)found=TRUE;candidate=GetNextArea();}
    if(!found || GetResRef(a)!=RWS(p,"area") || GetTag(a)!=RWS(p,"area_tag"))return OBJECT_INVALID;
    if(JsonGetType(JsonObjectGet(p,"x"))!=JsonGetType(JsonFloat(0.0))
        || JsonGetType(JsonObjectGet(p,"y"))!=JsonGetType(JsonFloat(0.0))
        || JsonGetType(JsonObjectGet(p,"z"))!=JsonGetType(JsonFloat(0.0))
        || JsonGetType(JsonObjectGet(p,"facing"))!=JsonGetType(JsonFloat(0.0)))return OBJECT_INVALID;
    return a;
}
location RWEncounterPoint(json p,object area)
{
    return Location(area,Vector(JsonGetFloat(JsonObjectGet(p,"x")),JsonGetFloat(JsonObjectGet(p,"y")),JsonGetFloat(JsonObjectGet(p,"z"))),JsonGetFloat(JsonObjectGet(p,"facing")));
}
int RWEncounterArm(object leader,json cmd)
{
    if(RWS(cmd,"world")!=RWWorld() || GetIsPC(leader) || GetIsDMPossessed(leader) || GetIsDead(leader))return FALSE;
    json p=JsonObjectGet(cmd,"policy"); json cast=JsonObjectGet(cmd,"actors");
    int radius=RWI(p,"trigger_radius"), leave=RWI(p,"leave_radius"), grace=RWI(p,"grace_seconds");
    int leash=RWI(p,"pursuit_radius"), hp=RWI(p,"retreat_hp_percent");
    string warning=RWS(p,"warning");
    if(RWS(p,"combat_mode")=="greeting" && JsonDump(JsonObjectGet(p,"attack"))!="false")return FALSE;
    // Boolean settings are JSON booleans, validated independently on the game side.
    if(JsonDump(JsonObjectGet(p,"enabled"))!="true"
        || (JsonDump(JsonObjectGet(p,"attack"))!="true" && JsonDump(JsonObjectGet(p,"attack"))!="false")
        || radius<1 || radius>8 || leave<=radius || leave>30 || grace<5 || grace>120
        || leash<0 || leash>60 || (leash>0 && leash<leave) || hp<0 || hp>90
        || GetStringLength(warning)<1 || GetStringLength(warning)>500
        || JsonGetLength(cast)<1 || JsonGetLength(cast)>8 || RWS(JsonArrayGet(cast,0),"npc")!=GetLocalString(leader,"rw_id"))return FALSE;
    if(RWS(p,"combat_mode")=="conversation" && ((RWS(cmd,"live_owner")=="" && RWS(cmd,"persistent_owner")=="") || JsonDump(JsonObjectGet(p,"attack"))!="true" || RWS(p,"combat_conditions")==""))return FALSE;
    string token=RWS(cmd,"token"); if(token=="")return FALSE;
    int permissionIndex;
    for(permissionIndex=0;permissionIndex<JsonGetLength(cast);permissionIndex++)
    {
        string combatant=JsonDump(JsonObjectGet(JsonArrayGet(cast,permissionIndex),"combatant"));
        // Missing means legacy combatant; a supplied value must be a real boolean.
        if(combatant!="null" && combatant!="true" && combatant!="false")return FALSE;
        if(GetStringLength(RWS(JsonArrayGet(cast,permissionIndex),"opening"))>300)return FALSE;
    }
    location anchor=GetLocation(leader);
    string owner=RWS(cmd,"live_owner");
    string persistent=RWS(cmd,"persistent_owner");
    if(owner!="" && persistent!="")return FALSE;
    if(persistent!="")
    {
        int k;
        for(k=0;k<JsonGetLength(cast);k++)
        {
            json row=JsonArrayGet(cast,k); object actor=RWFind(RWS(row,"npc"));
            if(!GetIsObjectValid(actor) || GetIsPC(actor) || GetIsDMPossessed(actor)
                || GetLocalString(actor,"rw_live_owner")!=""
                || GetLocalInt(actor,"rw_epoch")!=RWI(row,"epoch"))return FALSE;
        }
        for(k=0;k<JsonGetLength(cast);k++)
        {
            object actor=RWFind(RWS(JsonArrayGet(cast,k),"npc"));
            SetLocalString(actor,"rw_persistent_owner",persistent);
            SetLocalString(actor,"rw_persistent_scene",RWS(cmd,"encounter"));
        }
    }
    if(owner!="")
    {
        json point=JsonObjectGet(cmd,"anchor"); object area=RWEncounterPointArea(point);
        if(!GetIsObjectValid(area) || GetArea(leader)!=area
            || (JsonDump(JsonObjectGet(cmd,"repeat"))!="true" && JsonDump(JsonObjectGet(cmd,"repeat"))!="false"))return FALSE;
        int j;
        for(j=0;j<JsonGetLength(cast);j++)
        {
            object actor=RWFind(RWS(JsonArrayGet(cast,j),"npc"));
            if(GetLocalString(actor,"rw_live_owner")!=owner || GetLocalString(actor,"rw_live_scene")!=RWS(cmd,"encounter"))return FALSE;
        }
        anchor=RWEncounterPoint(point,area);
    }
    if(token!=GetLocalString(leader,"rw_enc_token"))
    {
        DeleteLocalObject(leader,"rw_enc_target");
        DeleteLocalInt(leader,"rw_enc_warning_seq");
        SetLocalString(leader,"rw_enc_token",token);
        SetLocalString(leader,"rw_enc_id",RWS(cmd,"encounter"));
        SetLocalString(leader,"rw_enc_cast",JsonDump(cast));
        SetLocalString(leader,"rw_enc_policy",JsonDump(p));
        SetLocalLocation(leader,"rw_enc_anchor",anchor);
        SetLocalInt(leader,"rw_enc_repeat",(owner=="" && persistent=="") || JsonDump(JsonObjectGet(cmd,"repeat"))=="true");
        DeleteLocalInt(leader,"rw_enc_reset_at");
        SetLocalString(leader,"rw_enc_status","armed");
        if(!RWEncounterCast(leader)){RWEncounterEvent(leader,"cancelled");return FALSE;}
        int i;
        for(i=0;i<JsonGetLength(cast);i++)
            SetLocalLocation(leader,"rw_enc_home_"+IntToString(i),GetLocation(RWFind(RWS(JsonArrayGet(cast,i),"npc"))));
    }
    else if(persistent!="")
    {
        // A companion restart may outlast the lease or an AUTO reset may change
        // epochs. Renew only the current, authenticated cast; recheck availability
        // before rearming. Never continue a half-finished warning after cancellation.
        SetLocalString(leader,"rw_enc_cast",JsonDump(cast));
        if(GetLocalString(leader,"rw_enc_status")=="cancelled" && RWEncounterCast(leader))
        {
            DeleteLocalObject(leader,"rw_enc_target");
            DeleteLocalInt(leader,"rw_enc_warning_seq");
            DeleteLocalInt(leader,"rw_enc_deadline");
            RWEncounterEvent(leader,"rearmed");
            SetLocalString(leader,"rw_enc_status","armed");
        }
    }
    if(token!=GetLocalString(leader,"rw_enc_reported"))
    {
        SetLocalString(leader,"rw_enc_reported",token);
        RWEncounterEvent(leader,"armed");
    }
    SetLocalInt(leader,"rw_director_hold",JsonDump(JsonObjectGet(cmd,"director_hold"))=="true");
    SetLocalInt(leader,"rw_enc_lease",GetLocalInt(GetModule(),"rw_tick")+5);
    return TRUE;
}
// Rearm only after a continuous quiet period. Keep the original anchor and homes;
// never respawn, heal, or revive actors as a side effect of resetting a trigger.
void RWEncounterReset(object leader)
{
    int tick=GetLocalInt(GetModule(),"rw_tick");
    if(tick>GetLocalInt(leader,"rw_enc_lease"))
    {DeleteLocalInt(leader,"rw_enc_reset_at");return;}
    if(!RWEncounterCast(leader))
    {DeleteLocalInt(leader,"rw_enc_reset_at");return;}
    json cast=JsonParse(GetLocalString(leader,"rw_enc_cast"));
    json p=JsonParse(GetLocalString(leader,"rw_enc_policy"));
    int i;
    for(i=0;i<JsonGetLength(cast);i++)
    {
        object npc=RWFind(RWS(JsonArrayGet(cast,i),"npc"));
        int hp=RWI(p,"retreat_hp_percent");
        if(GetDistanceBetweenLocations(GetLocation(npc),GetLocalLocation(leader,"rw_enc_home_"+IntToString(i)))>1.5
            || (GetLocalInt(npc,"rw_combat_active") && GetLocalString(npc,"rw_combat_phase")!="withdrawn")
            || (hp>0 && GetCurrentHitPoints(npc)*100<=GetMaxHitPoints(npc)*hp))
        {DeleteLocalInt(leader,"rw_enc_reset_at");return;}
    }
    location anchor=GetLocalLocation(leader,"rw_enc_anchor");
    object pc=GetFirstPC();
    while(GetIsObjectValid(pc))
    {
        if(RWEncounterPlayer(pc,GetAreaFromLocation(anchor))
            && GetDistanceBetweenLocations(GetLocation(pc),anchor)<=IntToFloat(RWI(p,"trigger_radius")))
        {DeleteLocalInt(leader,"rw_enc_reset_at");return;}
        pc=GetNextPC();
    }
    if(!GetLocalInt(leader,"rw_enc_reset_at"))
    {SetLocalInt(leader,"rw_enc_reset_at",tick+10);return;}
    if(tick<GetLocalInt(leader,"rw_enc_reset_at"))return;
    for(i=0;i<JsonGetLength(cast);i++)
        RWCombatRelease(RWFind(RWS(JsonArrayGet(cast,i),"npc")));
    DeleteLocalObject(leader,"rw_enc_target");
    DeleteLocalInt(leader,"rw_enc_deadline");
    DeleteLocalInt(leader,"rw_enc_reset_at");
    RWEncounterEvent(leader,"rearmed");
    SetLocalString(leader,"rw_enc_status","armed");
}
void RWEncounterAttack(object leader,object pc,json p,location anchor)
{
    // Do not target bystanders or change a global faction. Native creature AI owns combat.
    json cast=JsonParse(GetLocalString(leader,"rw_enc_cast")); int i;
    for(i=0;i<JsonGetLength(cast);i++)
    {
        json actor=JsonArrayGet(cast,i);
        // Hostages and witnesses remain part of the story without joining its attack.
        if(JsonDump(JsonObjectGet(actor,"combatant"))=="false")continue;
        object npc=RWFind(RWS(actor,"npc"));
        RWCombatRelease(npc);
        if(RWI(p,"pursuit_radius")>0 || RWI(p,"retreat_hp_percent")>0)
        {
            SetLocalInt(npc,"rw_combat_active",TRUE);
            DeleteLocalInt(npc,"rw_combat_return_reported");
            DeleteLocalString(npc,"rw_combat_reason");
            SetLocalInt(npc,"rw_combat_epoch",GetLocalInt(npc,"rw_epoch"));
            SetLocalInt(npc,"rw_combat_leash",RWI(p,"pursuit_radius"));
            SetLocalInt(npc,"rw_combat_hp",RWI(p,"retreat_hp_percent"));
            SetLocalLocation(npc,"rw_combat_home",GetLocalLocation(leader,"rw_enc_home_"+IntToString(i)));
            SetLocalLocation(npc,"rw_combat_anchor",anchor);
            SetLocalObject(npc,"rw_combat_target",pc);
            SetLocalString(npc,"rw_combat_id",GetLocalString(leader,"rw_enc_id"));
            SetLocalString(npc,"rw_combat_token",GetLocalString(leader,"rw_enc_token"));
            SetLocalString(npc,"rw_combat_phase","fighting");
        }
        SetLocalString(npc,"rw_action_status","interrupted");
        AssignCommand(npc,ClearAllActions(TRUE));
        AssignCommand(npc,ActionAttack(pc));
    }
    RWEncounterEvent(leader,"attack");
}
// Called only after reviewed dialogue was delivered. The target comes from the
// authenticated game chat, never a model-supplied name or object ID.
int RWEncounterDecision(object leader,object pc,json cmd)
{
    json p=JsonParse(GetLocalString(leader,"rw_enc_policy"));
    int tick=GetLocalInt(GetModule(),"rw_tick");
    location anchor=GetLocalLocation(leader,"rw_enc_anchor");
    string status=GetLocalString(leader,"rw_enc_status");
    string choice=RWS(cmd,"encounter_choice");
    if(GetLocalInt(leader,"rw_director_hold") || RWS(p,"combat_mode")!="conversation" || JsonDump(JsonObjectGet(p,"attack"))!="true"
        || RWS(cmd,"world")!=RWWorld() || RWS(cmd,"token")!=GetLocalString(leader,"rw_enc_token")
        || RWS(cmd,"encounter")!=GetLocalString(leader,"rw_enc_id")
        || !RWEncounterOwner(leader,cmd)
        || tick>GetLocalInt(leader,"rw_enc_lease") || !RWEncounterCast(leader)
        || (status!="armed" && status!="engaged" && status!="negotiating")
        || !RWEncounterPlayer(pc,GetAreaFromLocation(anchor)) || GetIsInCombat(pc)
        || GetDistanceBetweenLocations(GetLocation(pc),anchor)>=IntToFloat(RWI(p,"leave_radius"))
        || !LineOfSightObject(leader,pc) || !GetObjectSeen(pc,leader)
        || RWS(cmd,"combat_event")=="" || RWS(cmd,"combat_event")!=GetLocalString(leader,"rw_enc_chat_event")
        || pc!=GetLocalObject(leader,"rw_enc_chat_pc"))return FALSE;
    if((status=="engaged" || status=="negotiating") && pc!=GetLocalObject(leader,"rw_enc_target"))return FALSE;
    if(choice=="encounter:stand_down") {RWEncounterEvent(leader,"peaceful");return TRUE;}
    if(choice=="encounter:warn")
    {
        if(status!="armed" && status!="engaged")return FALSE;
        if(!NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK,RWS(p,"warning"),leader))return FALSE;
        SendMessageToPC(pc,GetName(leader)+": "+RWS(p,"warning")+" (You may leave safely; combat requires a later reply.)");
        SetLocalObject(leader,"rw_enc_target",pc);
        SetLocalInt(leader,"rw_enc_warning_seq",GetLocalInt(leader,"rw_enc_chat_seq"));
        SetLocalInt(leader,"rw_enc_deadline",tick+RWI(p,"grace_seconds"));
        SetLocalInt(leader,"rw_enc_warning_expiry",tick+RWI(p,"grace_seconds")+120);
        RWEncounterEvent(leader,"negotiating");return TRUE;
    }
    if(choice!="encounter:attack" || status!="negotiating"
        || tick<GetLocalInt(leader,"rw_enc_deadline") || tick>GetLocalInt(leader,"rw_enc_warning_expiry")
        || GetLocalInt(leader,"rw_enc_chat_seq")<=GetLocalInt(leader,"rw_enc_warning_seq"))return FALSE;
    RWEncounterAttack(leader,pc,p,anchor);return TRUE;
}
object RWEncounterNearbyPlayer(object leader,json p,location anchor)
{
        object candidate=GetFirstPC(); float best=IntToFloat(RWI(p,"trigger_radius"))+0.01;
        object pc=OBJECT_INVALID;
        while(GetIsObjectValid(candidate))
        {
            if(RWEncounterPlayer(candidate,GetAreaFromLocation(anchor)) && !GetIsInCombat(candidate))
            {
                float distance=GetDistanceBetweenLocations(GetLocation(candidate),anchor);
                if(distance<best && LineOfSightObject(leader,candidate) && GetObjectSeen(candidate,leader)
                    && RWCanHear(candidate,leader,RWHearingRange())){pc=candidate;best=distance;}
            }
            candidate=GetNextPC();
        }
        return pc;
}
// The director may end an activation, never initiate combat or choose a target.
// Cast banter cannot spend gold, choose targets, or advance a conversation turn.
// Authenticate both actors against the current scene and require a visible player.
int RWSceneSpeech(object npc,object peer,json cmd)
{
    object leader=RWFind(RWS(cmd,"leader"));
    if(!GetIsObjectValid(leader) || !RWEncounterOwner(leader,cmd) || !RWEncounterOwner(npc,cmd) || !RWEncounterOwner(peer,cmd)
        || RWS(cmd,"token")!=GetLocalString(leader,"rw_enc_token")
        || GetLocalInt(GetModule(),"rw_tick")>GetLocalInt(leader,"rw_enc_lease") || GetLocalInt(leader,"rw_director_hold"))return FALSE;
    string status=GetLocalString(leader,"rw_enc_status");
    if(status!="engaged" && status!="negotiating")return FALSE;
    json cast=JsonParse(GetLocalString(leader,"rw_enc_cast"));int i,a=FALSE,b=FALSE;
    for(i=0;i<JsonGetLength(cast);i++)
    {json row=JsonArrayGet(cast,i);object o=RWFind(RWS(row,"npc"));if(GetLocalInt(o,"rw_epoch")==RWI(row,"epoch")){if(o==npc)a=TRUE;if(o==peer)b=TRUE;}}
    if(!a || !b)return FALSE;
    object pc=GetFirstPC();while(GetIsObjectValid(pc))
    {if(RWEncounterPlayer(pc,GetArea(npc)) && GetDistanceBetween(pc,npc)<=15.0 && LineOfSightObject(npc,pc))return TRUE;pc=GetNextPC();}
    return FALSE;
}
int RWEncounterEnd(object leader,json cmd)
{
    if(RWS(cmd,"world")!=RWWorld() || RWS(cmd,"token")!=GetLocalString(leader,"rw_enc_token")
        || RWS(cmd,"encounter")!=GetLocalString(leader,"rw_enc_id")
        || !RWEncounterOwner(leader,cmd)
        || GetLocalInt(GetModule(),"rw_tick")>GetLocalInt(leader,"rw_enc_lease"))return FALSE;
    json cast=JsonParse(GetLocalString(leader,"rw_enc_cast"));int i;
    if(JsonGetLength(cast)<1 || JsonGetLength(cast)>8)return FALSE;
    for(i=0;i<JsonGetLength(cast);i++)
    {
        json row=JsonArrayGet(cast,i);object actor=RWFind(RWS(row,"npc"));
        if(!GetIsObjectValid(actor) || !RWEncounterOwner(actor,cmd)
            || GetIsDMPossessed(actor) || (!GetIsDead(actor) && GetIsInCombat(actor))
            || GetLocalInt(actor,"rw_epoch")!=RWI(row,"epoch"))return FALSE;
    }
    SetLocalInt(leader,"rw_enc_repeat",FALSE);
    SetLocalInt(leader,"rw_director_hold",TRUE);
    RWEncounterEvent(leader,"director_finished");return TRUE;
}
void RWDirectorObserve(object leader)
{
    int tick=GetLocalInt(GetModule(),"rw_tick");
    if((GetLocalString(leader,"rw_live_owner")=="" && GetLocalString(leader,"rw_persistent_owner")=="") || tick>GetLocalInt(leader,"rw_enc_lease")
        || tick<GetLocalInt(leader,"rw_director_observe_at"))return;
    SetLocalInt(leader,"rw_director_observe_at",tick+5);
    location anchor=GetLocalLocation(leader,"rw_enc_anchor");
    json policy=JsonParse(GetLocalString(leader,"rw_enc_policy"));
    json players=JsonArray();object pc=GetFirstPC();
    while(GetIsObjectValid(pc) && JsonGetLength(players)<32)
    {
        if(RWEncounterPlayer(pc,GetAreaFromLocation(anchor))
            && GetDistanceBetweenLocations(GetLocation(pc),anchor)<=IntToFloat(RWI(policy,"leave_radius"))
            && LineOfSightObject(leader,pc))
            players=JsonArrayInsert(players,JsonString(GetPCPublicCDKey(pc)+":"+GetName(pc)));
        pc=GetNextPC();
    }
    json e=RWBase("director_observation",leader);
    e=JsonObjectSet(e,"encounter",JsonString(GetLocalString(leader,"rw_enc_id")));
    e=JsonObjectSet(e,"token",JsonString(GetLocalString(leader,"rw_enc_token")));
    e=JsonObjectSet(e,"players",players);RWEmit(e);
}
void RWCastOpening(object leader,object pc,string token,int index,int generation)
{
    if(!GetIsObjectValid(leader) || GetLocalString(leader,"rw_mode")!="auto" || GetIsDead(leader) || GetIsDMPossessed(leader) || GetIsInCombat(leader) || token!=GetLocalString(leader,"rw_enc_token")
        || generation!=GetLocalInt(leader,"rw_cast_opening_generation")
        || GetLocalInt(GetModule(),"rw_tick")>GetLocalInt(leader,"rw_enc_lease"))return;
    string status=GetLocalString(leader,"rw_enc_status");
    if(status!="engaged" && status!="negotiating")return;
    json row=JsonArrayGet(JsonParse(GetLocalString(leader,"rw_enc_cast")),index);
    object npc=RWFind(RWS(row,"npc"));string speech=RWS(row,"opening");
    if(speech=="" || !GetIsObjectValid(npc) || GetLocalInt(npc,"rw_epoch")!=RWI(row,"epoch")
        || GetLocalString(npc,"rw_mode")!="auto" || GetIsDead(npc) || GetIsDMPossessed(npc) || GetIsInCombat(npc)
        || !RWEncounterPlayer(pc,GetArea(npc)) || GetDistanceBetween(pc,npc)>20.0 || !LineOfSightObject(npc,pc))return;
    if(NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK,speech,npc))
    {
        json e=RWBase("scene_line",npc);e=JsonObjectSet(e,"encounter",JsonString(GetLocalString(leader,"rw_enc_id")));
        e=JsonObjectSet(e,"token",JsonString(token));e=JsonObjectSet(e,"text",JsonString(speech));RWEmit(e);
    }
}
void RWEncounterTick(object leader)
{
    RWDirectorObserve(leader);
    string status=GetLocalString(leader,"rw_enc_status");
    if(status=="attack" || status=="left" || status=="finished" || status=="peaceful")
    {if(GetLocalInt(leader,"rw_enc_repeat"))RWEncounterReset(leader);return;}
    if(status!="armed" && status!="engaged" && status!="warning" && status!="negotiating")return;
    int tick=GetLocalInt(GetModule(),"rw_tick");
    if(tick>GetLocalInt(leader,"rw_enc_lease") || !RWEncounterCast(leader))
    {RWEncounterEvent(leader,"cancelled");return;}
    json p=JsonParse(GetLocalString(leader,"rw_enc_policy"));
    location anchor=GetLocalLocation(leader,"rw_enc_anchor");
    object pc=GetLocalObject(leader,"rw_enc_target");
    if(RWS(p,"combat_mode")=="conversation" || RWS(p,"combat_mode")=="greeting")
    {
        if(status=="armed")
        {
            pc=RWEncounterNearbyPlayer(leader,p,anchor);
            if(!GetIsObjectValid(pc))return;
            // Do not steal a player's active conversation with another NPC.
            object talking=RWCurrentTalk(pc);
            if(GetIsObjectValid(talking) && talking!=leader)return;
            string opening=RWS(p,"opening");
            if(opening=="")opening="A moment, traveler. I would like a word.";
            if(GetStringLength(opening)>500 || !NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK,opening,leader))
            {RWEncounterEvent(leader,"warning_failed");return;}
            SetLocalObject(leader,"rw_enc_target",pc);
            RWBeginTalk(pc,leader);
            RWEncounterEvent(leader,"engaged");
            int generation=GetLocalInt(leader,"rw_cast_opening_generation")+1;SetLocalInt(leader,"rw_cast_opening_generation",generation);
            json cast=JsonParse(GetLocalString(leader,"rw_enc_cast"));int i,pass,slot=1;
            // Witnesses/captives speak first. These DM-authored lines don't wait
            // for an LLM and do not steal the player's selected conversation.
            for(pass=0;pass<2;pass++)for(i=1;i<JsonGetLength(cast);i++)
            {
                json actor=JsonArrayGet(cast,i);int captive=JsonDump(JsonObjectGet(actor,"combatant"))=="false";
                if(RWS(actor,"opening")!="" && ((pass==0 && captive) || (pass==1 && !captive)))
                {DelayCommand(IntToFloat(slot*3),RWCastOpening(leader,pc,GetLocalString(leader,"rw_enc_token"),i,generation));slot++;}
            }
            return;
        }
        if((status=="engaged" || status=="negotiating") && (!RWEncounterPlayer(pc,GetAreaFromLocation(anchor))
            || GetDistanceBetweenLocations(GetLocation(pc),anchor)>=IntToFloat(RWI(p,"leave_radius"))))
            RWEncounterEvent(leader,"left");
        else if(status=="negotiating" && tick>GetLocalInt(leader,"rw_enc_warning_expiry"))
            RWEncounterEvent(leader,"peaceful");
        return; // No timer-driven attacks in conversation mode.
    }
    if(status=="armed")
    {
        pc=RWEncounterNearbyPlayer(leader,p,anchor);
        if(!GetIsObjectValid(pc))return;
        if(!NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK,RWS(p,"warning"),leader))
        {RWEncounterEvent(leader,"warning_failed");return;}
        // The private copy makes the warning unambiguous for the selected target.
        SendMessageToPC(pc,GetName(leader)+": "+RWS(p,"warning")+" (Move at least "+IntToString(RWI(p,"leave_radius"))+" metres from the encounter start within "+IntToString(RWI(p,"grace_seconds"))+" seconds.)");
        SetLocalObject(leader,"rw_enc_target",pc);
        SetLocalInt(leader,"rw_enc_deadline",tick+RWI(p,"grace_seconds"));
        RWEncounterEvent(leader,"warning");return;
    }
    if(!RWEncounterPlayer(pc,GetAreaFromLocation(anchor))
        || GetDistanceBetweenLocations(GetLocation(pc),anchor)>=IntToFloat(RWI(p,"leave_radius")))
    {RWEncounterEvent(leader,"left");return;}
    if(tick<GetLocalInt(leader,"rw_enc_deadline"))return;
    if(JsonDump(JsonObjectGet(p,"attack"))!="true")
    {RWEncounterEvent(leader,"finished");return;}
    if(!LineOfSightObject(leader,pc) || !GetObjectSeen(pc,leader))
    {RWEncounterEvent(leader,"cancelled");return;}
    RWEncounterAttack(leader,pc,p,anchor);
}
