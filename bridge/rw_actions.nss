#include "rw_inc"
// Fixed game-side allowlist. No model-supplied scripts, targets or animation numbers.
int RWActionUniqueArea(object area)
{
    int matches=0; object a=GetFirstArea();
    while(GetIsObjectValid(a)) { if(GetResRef(a)==GetResRef(area) && GetTag(a)==GetTag(area)) matches++; a=GetNextArea(); }
    return matches==1;
}
void RWActionEnd(object npc, string status)
{
    if (GetLocalString(npc,"rw_action_status") != "running" && GetLocalString(npc,"rw_action_status") != "waiting for player") return;
    SetLocalString(npc,"rw_action_status",status);
    if (!GetIsDMPossessed(npc)) AssignCommand(npc,ClearAllActions(TRUE));
    if (status == "completed") RWPlacement(npc);
}
void RWActionTick(object npc)
{
    if (GetLocalString(npc,"rw_action_status") != "running" && GetLocalString(npc,"rw_action_status") != "waiting for player") return;
    int tick=GetLocalInt(GetModule(),"rw_tick");
    if(GetLocalInt(npc,"rw_action_patrol") && RWHasConversation(npc))
    { RWActionEnd(npc,"interrupted"); return; }
    if (GetIsDMPossessed(npc) || GetIsDead(npc) || GetIsInCombat(npc) || GetLocalString(npc,"rw_mode")!="auto"
        || GetLocalInt(npc,"rw_action_epoch")!=GetLocalInt(npc,"rw_epoch"))
        RWActionEnd(npc,"interrupted");
    else if (GetLocalString(npc,"rw_action_kind")=="walk" || GetLocalString(npc,"rw_action_kind")=="home" || GetLocalString(npc,"rw_action_kind")=="lead")
    {
        location dest=GetLocalLocation(npc,"rw_action_destination");
        if(GetLocalString(npc,"rw_action_kind")=="lead")
        {
            object pc=GetLocalObject(npc,"rw_action_player");
            if(!GetIsObjectValid(pc) || GetIsDead(pc) || GetArea(pc)!=GetArea(npc) || GetDistanceBetween(pc,npc)>20.0)
            {RWActionEnd(npc,"player unavailable");return;}
            if(tick>=GetLocalInt(npc,"rw_action_deadline")){RWActionEnd(npc,"timed out");return;}
            if(GetDistanceBetween(pc,npc)>6.0 || !LineOfSightObject(pc,npc))
            {
                if(GetLocalString(npc,"rw_action_status")!="waiting for player")
                {
                    AssignCommand(npc,ClearAllActions(TRUE));SetLocalString(npc,"rw_action_status","waiting for player");
                    SetLocalInt(npc,"rw_action_wait_until",tick+30);
                }
                if(tick>=GetLocalInt(npc,"rw_action_wait_until"))RWActionEnd(npc,"player did not catch up");
                return;
            }
            if(GetLocalString(npc,"rw_action_status")=="waiting for player")
            {SetLocalString(npc,"rw_action_status","running");AssignCommand(npc,ActionMoveToLocation(dest,FALSE));}
        }
        if (GetArea(npc)!=GetAreaFromLocation(dest)) RWActionEnd(npc,"interrupted");
        else if (GetDistanceBetweenLocations(GetLocation(npc),dest)<=1.5) RWActionEnd(npc,"completed");
        else if (tick>=GetLocalInt(npc,"rw_action_deadline")) RWActionEnd(npc,"timed out");
    }
    else if (tick>=GetLocalInt(npc,"rw_action_deadline")) RWActionEnd(npc,"completed");
}
int RWStartAction(object npc,json cmd)
{
    object m=GetModule(); int tick=GetLocalInt(m,"rw_tick");
    string kind=RWS(cmd,"action");
    if(RWI(cmd,"patrol") && (kind!="walk" || RWHasConversation(npc))) return FALSE;
    if (RWS(cmd,"world")!=RWWorld() || GetLocalString(npc,"rw_mode")!="auto" || GetIsDMPossessed(npc) || GetIsDead(npc) || GetIsInCombat(npc)
        || GetLocalString(npc,"rw_action_status")=="running" || GetLocalString(npc,"rw_action_status")=="waiting for player" || (kind!="shop" && tick<GetLocalInt(npc,"rw_action_next"))
        || GetStringLength(RWS(cmd,"request"))!=24 || RWS(cmd,"request")==GetLocalString(npc,"rw_action_request")) return FALSE;
    string listener=RWS(cmd,"listener");
    if (listener!="" && (!RWCanHear(StringToObject(listener),npc,RWHearingRange())
        || RWS(cmd,"conversation_revision")!=GetLocalString(m,"rw_talk_revision"))) return FALSE;
    int animation=-1;
    location dest=GetLocation(npc);
    if (kind=="walk" || kind=="lead" || kind=="home")
    {
        json d=JsonObjectGet(cmd,"destination"); object area=GetArea(npc);
        if (RWS(d,"world")!=RWWorld() || RWS(d,"id")!=RWS(cmd,"target") || GetResRef(area)!=RWS(d,"area") || GetTag(area)!=RWS(d,"area_tag")) return FALSE;
        if (!RWActionUniqueArea(area) || JsonGetType(JsonObjectGet(d,"x"))!=JsonGetType(JsonFloat(0.0))
            || JsonGetType(JsonObjectGet(d,"y"))!=JsonGetType(JsonFloat(0.0)) || JsonGetType(JsonObjectGet(d,"z"))!=JsonGetType(JsonFloat(0.0))
            || JsonGetType(JsonObjectGet(d,"facing"))!=JsonGetType(JsonFloat(0.0))) return FALSE;
        vector v=Vector(JsonGetFloat(JsonObjectGet(d,"x")),JsonGetFloat(JsonObjectGet(d,"y")),JsonGetFloat(JsonObjectGet(d,"z")));
        dest=Location(area,v,JsonGetFloat(JsonObjectGet(d,"facing")));
        if (GetDistanceBetweenLocations(GetLocation(npc),dest)>40.0) return FALSE;
    }
    else if(kind=="shop")
    {
        int ok=FALSE;
        if(RWS(cmd,"target")=="open")ok=RWShopOpen(npc,StringToObject(listener));
        if(RWS(cmd,"target")=="haggle")ok=RWShopHaggle(npc,StringToObject(listener));
        if(!ok)return FALSE;
        SetLocalString(npc,"rw_action_request",RWS(cmd,"request"));SetLocalString(npc,"rw_action_kind","shop");
        SetLocalString(npc,"rw_action_status","shop opened");return TRUE;
    }
    else if (kind=="gesture")
    {
        if (RWS(cmd,"target")=="greet") animation=ANIMATION_FIREFORGET_GREETING;
        if (RWS(cmd,"target")=="bow") animation=ANIMATION_FIREFORGET_BOW;
        if (RWS(cmd,"target")=="salute") animation=ANIMATION_FIREFORGET_SALUTE;
        if (animation<0) return FALSE;
    }
    else return FALSE;
    if(kind=="lead")
    {
        object pc=StringToObject(listener);
        if(!GetIsObjectValid(pc) || !GetIsPC(pc) || GetIsDM(pc) || GetIsDMPossessed(pc) || GetIsDead(pc) || !RWCanHear(pc,npc,6.0))return FALSE;
        SetLocalObject(npc,"rw_action_player",pc);
    }
    SetLocalString(npc,"rw_action_request",RWS(cmd,"request"));
    SetLocalInt(npc,"rw_action_patrol",RWI(cmd,"patrol"));
    SetLocalString(npc,"rw_action_status","running");
    SetLocalString(npc,"rw_action_kind",kind);
    SetLocalInt(npc,"rw_action_epoch",GetLocalInt(npc,"rw_epoch"));
    SetLocalInt(npc,"rw_action_next",tick+20);
    SetLocalInt(npc,"rw_action_deadline",tick+3);
    AssignCommand(npc,ClearAllActions(TRUE));
    if (kind=="walk" || kind=="lead" || kind=="home")
    {
        SetLocalLocation(npc,"rw_action_destination",dest);
        SetLocalInt(npc,"rw_action_deadline",tick+30);
        if(kind=="lead")SetLocalInt(npc,"rw_action_deadline",tick+120);
        AssignCommand(npc,ActionMoveToLocation(dest,FALSE));
    }
    else AssignCommand(npc,ActionPlayAnimation(animation,1.0,1.0));
    return TRUE;
}
void RWCaptureAction(json cmd)
{
    object m=GetModule(); int tick=GetLocalInt(m,"rw_tick");
    json result=RWBase("action_capture",OBJECT_INVALID);
    result=JsonObjectSet(result,"request",JsonString(RWS(cmd,"request")));
    int ok=FALSE;
    if (GetLocalInt(m,"rw_allow_dm_spawn") && RWS(cmd,"world")==RWWorld() && RWS(cmd,"session")==GetLocalString(m,"rw_session")
        && RWI(cmd,"expires")>=tick && RWI(cmd,"expires")<=tick+5)
    {
        object dm=StringToObject(RWS(cmd,"dm")); object area=GetArea(dm);
        if (GetIsObjectValid(dm) && GetIsDM(dm) && !GetIsDMPossessed(dm) && GetIsObjectValid(area)
            && GetLocalString(dm,"rw_dm_token")==RWS(cmd,"token"))
        {
            if(RWActionUniqueArea(area) && GetTag(area)!="")
            {
                vector p=GetPosition(dm);
                result=JsonObjectSet(result,"area",JsonString(GetResRef(area)));
                result=JsonObjectSet(result,"area_tag",JsonString(GetTag(area)));
                result=JsonObjectSet(result,"x",JsonFloat(p.x));result=JsonObjectSet(result,"y",JsonFloat(p.y));result=JsonObjectSet(result,"z",JsonFloat(p.z));
                result=JsonObjectSet(result,"facing",JsonFloat(GetFacing(dm)));ok=TRUE;
            }
        }
    }
    result=JsonObjectSet(result,"ok",JsonInt(ok));RWEmit(result);
}
