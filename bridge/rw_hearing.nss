// Optional familiar hearing. A bounded in-memory buffer, never Redis traffic,
// LLM work or a persistent chat log. Owner commands remain a separate path.
#include "rw_cp_prefs"

void RWCPHearClear(object familiar)
{
    DeleteLocalString(familiar,"rw_heard");DeleteLocalObject(familiar,"rw_heard_area");
    DeleteLocalObject(familiar,"rw_heard_owner");DeleteLocalString(familiar,"rw_heard_session");
    DeleteLocalString(familiar,"rw_heard_generation");
}
int RWCPHearEnabled(object owner,object familiar)
{
    return GetLocalInt(GetModule(),"rw_cp_enabled") && GetLocalInt(GetModule(),"rw_cp_listening")
        && GetIsPC(owner) && !GetIsDM(owner) && !GetIsDead(owner) && !GetIsDMPossessed(owner)
        && GetLocalInt(owner,"rw_cp_on") && GetLocalString(owner,"rw_cp_login_session")==GetLocalString(GetModule(),"rw_session")
        && RWCPPreferencesReady(owner) && RWCPPreference(owner,"listening")
        && GetIsObjectValid(familiar) && familiar==RWCPFind(owner) && GetMaster(familiar)==owner
        && !GetIsDead(familiar) && !GetIsDMPossessed(familiar) && !GetIsPossessedFamiliar(familiar)
        && GetArea(owner)==GetArea(familiar);
}
// Strictly public Talk. Private targets, whispers, party, tells, DM/OOC and
// helper commands never enter the buffer, even when displayed near the player.
int RWCPHearPublicText(object speaker,string text,int channel,object target=OBJECT_INVALID)
{
    if(channel!=NWNX_CHAT_CHANNEL_PLAYER_TALK || GetIsObjectValid(target)
        || !GetIsObjectValid(speaker) || GetObjectType(speaker)!=OBJECT_TYPE_CREATURE
        || GetIsDM(speaker) || GetIsDMPossessed(speaker) || GetIsPossessedFamiliar(speaker)
        || GetIsDead(speaker) || GetStringLength(text)>2000)return FALSE;
    while(GetStringLeft(text,1)==" " || GetStringLeft(text,1)=="\t" || GetStringLeft(text,1)=="\n" || GetStringLeft(text,1)=="\r")
        text=GetSubString(text,1,GetStringLength(text));
    return text!="" && GetStringLeft(text,1)!="/" && GetStringLeft(text,1)!="!" && GetStringLeft(text,2)!="((";
}
int RWCPHearAudible(object familiar,object speaker)
{
    return familiar!=speaker && GetIsObjectValid(familiar) && GetIsObjectValid(speaker)
        && GetArea(familiar)==GetArea(speaker) && GetDistanceBetween(familiar,speaker)<=RWHearingRange()
        && LineOfSightObject(familiar,speaker) && RWAreaCreatureVisible(familiar,speaker);
}
json RWCPHearPrune(json rows,int tick)
{
    json kept=JsonArray();int i,start=JsonGetLength(rows)-8;if(start<0)start=0;
    for(i=start;i<JsonGetLength(rows);i++)
    {
        json row=JsonArrayGet(rows,i);int when=RWI(row,"tick");
        if(when<=tick && tick-when<=120)kept=JsonArrayInsert(kept,row);
    }
    return kept;
}
json RWCPHearRecent(object familiar)
{
    object owner=GetMaster(familiar),m=GetModule();
    if(!RWCPHearEnabled(owner,familiar)) {RWCPHearClear(familiar);return JsonArray();}
    if(GetLocalObject(familiar,"rw_heard_area")!=GetArea(familiar)
        || GetLocalObject(familiar,"rw_heard_owner")!=owner
        || GetLocalString(familiar,"rw_heard_session")!=GetLocalString(m,"rw_session")
        || GetLocalString(familiar,"rw_heard_generation")!=GetLocalString(m,"rw_cpp_generation"))
        RWCPHearClear(familiar);
    SetLocalObject(familiar,"rw_heard_area",GetArea(familiar));SetLocalObject(familiar,"rw_heard_owner",owner);
    SetLocalString(familiar,"rw_heard_session",GetLocalString(m,"rw_session"));
    SetLocalString(familiar,"rw_heard_generation",GetLocalString(m,"rw_cpp_generation"));
    json rows=RWCPHearPrune(JsonParse(GetLocalString(familiar,"rw_heard")),GetLocalInt(m,"rw_tick"));
    SetLocalString(familiar,"rw_heard",JsonDump(rows));return rows;
}
void RWCPHearPublic(object speaker,string text,int channel=NWNX_CHAT_CHANNEL_PLAYER_TALK,object target=OBJECT_INVALID)
{
    if(!RWCPHearPublicText(speaker,text,channel,target) || !GetLocalInt(GetModule(),"rw_cp_listening"))return;
    object owner=GetFirstPC();int scanned=0;
    while(GetIsObjectValid(owner) && scanned<256)
    {
        object familiar=RWCPFind(owner);
        if(RWCPHearEnabled(owner,familiar) && RWCPHearAudible(familiar,speaker))
        {
            json rows=RWCPHearRecent(familiar),row=JsonObject();
            string kind=GetIsPC(speaker)?(speaker==owner?"owner":"player"):"npc";
            row=JsonObjectSet(row,"speaker_kind",JsonString(kind));
            row=JsonObjectSet(row,"speaker",JsonString(GetIsPC(speaker)?"Unidentified traveler":GetStringLeft(GetName(speaker),80)));
            row=JsonObjectSet(row,"appearance",JsonString(RWVisibleAppearance(speaker)));
            row=JsonObjectSet(row,"channel",JsonString("talk"));
            row=JsonObjectSet(row,"tick",JsonInt(GetLocalInt(GetModule(),"rw_tick")));
            row=JsonObjectSet(row,"text",JsonString(GetStringLeft(text,400)));
            rows=RWCPHearPrune(JsonArrayInsert(rows,row),GetLocalInt(GetModule(),"rw_tick"));
            SetLocalString(familiar,"rw_heard",JsonDump(rows));
        }
        owner=GetNextPC();scanned++;
    }
}
