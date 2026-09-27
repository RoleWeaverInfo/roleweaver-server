// Live placement and cleanup use session-scoped ownership, never proximity deletion.
#include "rw_inc"
#include "rw_encounter"
int RWLiveCommand(json cmd)
{
    object m=GetModule(); int tick=GetLocalInt(m,"rw_tick");
    string id=RWS(cmd,"npc"), owner=RWS(cmd,"owner"), scene=RWS(cmd,"scene");
    if(!GetLocalInt(m,"rw_allow_dm_spawn") || RWS(cmd,"world")!=RWWorld()
        || RWS(cmd,"session")!=GetLocalString(m,"rw_session")
        || RWI(cmd,"expires")<tick || RWI(cmd,"expires")>tick+5
        || !RWValidID(id) || !RWValidID(scene) || GetStringLength(owner)!=24)return FALSE;
    object npc=RWFind(id);
    if(RWS(cmd,"kind")=="live_cleanup")
    {
        // Cancel queued spawns too, including a placement whose acknowledgement was lost.
        SetLocalInt(m,"rw_live_closed_"+owner,TRUE);
        if(!GetIsObjectValid(npc))return TRUE;
        if(GetLocalString(npc,"rw_live_owner")!=owner || GetLocalString(npc,"rw_live_scene")!=scene
            || GetLocalString(npc,"rw_source")!="dm_temporary" || GetIsPC(npc) || GetIsDMPossessed(npc))return FALSE;
        SetLocalString(npc,"rw_enc_status","cancelled");
        RWMode(npc,"paused");
        ExecuteScript("rw_unbind",npc);
        DestroyObject(npc);return TRUE;
    }
    if(RWS(cmd,"kind")!="live_spawn" || GetLocalInt(m,"rw_live_closed_"+owner))return FALSE;
    if(GetIsObjectValid(npc))return GetLocalString(npc,"rw_live_owner")==owner;
    object dm=StringToObject(RWS(cmd,"dm"));
    if(!GetIsObjectValid(dm) || !GetIsDM(dm) || GetIsDMPossessed(dm)
        || GetLocalString(dm,"rw_dm_token")!=RWS(cmd,"dm_token") || !RWHasSlot())return FALSE;
    json point=JsonObjectGet(cmd,"point"); object area=RWEncounterPointArea(point);
    if(!GetIsObjectValid(area))return FALSE;
    string blueprint=RWS(cmd,"blueprint");
    if(GetStringLength(blueprint)<1 || GetStringLength(blueprint)>16 || !RWValidID(blueprint))return FALSE;
    location dest=RWEncounterPoint(point,area);
    if(blueprint=="rw_custom")npc=RWCreateCreature(JsonObjectGet(cmd,"creature"),dest);
    else npc=CreateObject(OBJECT_TYPE_CREATURE,blueprint,dest);
    if(!GetIsObjectValid(npc))return FALSE;
    SetLocalString(npc,"rw_live_owner",owner);
    SetLocalString(npc,"rw_live_scene",scene);
    SetLocalString(npc,"rw_source","dm_temporary");
    SetName(npc,GetStringLeft(RWS(cmd,"name"),80));
    SetTag(npc,"rw_temp_"+id);
    RWBind(npc,id,dm);
    if(RWFind(id)!=npc){DestroyObject(npc);return FALSE;}
    // Placement does not arm a trigger or enable LLM dialogue. DM starts explicitly.
    RWMode(npc,"paused");
    SetLocalInt(npc,"rw_live_commandable",GetCommandable(npc));
    SetLocalInt(npc,"rw_live_staged",TRUE);
    AssignCommand(npc,ClearAllActions(TRUE));
    SetCommandable(FALSE,npc);return TRUE;
}
