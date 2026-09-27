// Optional NWN resolver. The model never supplies dice, bonuses, DCs or scripts.
#include "rw_inc"
int RWSocialSkill(string name)
{
    if(name=="intimidate")return SKILL_INTIMIDATE;
    if(name=="persuade")return SKILL_PERSUADE;
    if(name=="bluff")return SKILL_BLUFF;
    return -1;
}
int RWSocialOwner(object npc,json cmd)
{
    string live=RWS(cmd,"live_owner"), persistent=RWS(cmd,"persistent_owner");
    int owned=(live!="" && persistent=="" && live==GetLocalString(npc,"rw_live_owner")
        && RWS(cmd,"encounter")==GetLocalString(npc,"rw_live_scene"))
        || (live=="" && persistent!="" && GetLocalString(npc,"rw_live_owner")==""
        && persistent==GetLocalString(npc,"rw_persistent_owner")
        && RWS(cmd,"encounter")==GetLocalString(npc,"rw_persistent_scene"));
    return RWS(cmd,"world")==RWWorld() && owned
        && !GetIsPC(npc) && !GetIsDead(npc) && !GetIsDMPossessed(npc)
        && !GetIsInCombat(npc) && GetLocalString(npc,"rw_mode")=="auto";
}
int RWSocialSetup(object npc,json cmd)
{
    if(!RWSocialOwner(npc,cmd) || RWS(cmd,"token")=="")return FALSE;
    json p=JsonObjectGet(cmd,"settings");
    if(JsonDump(JsonObjectGet(p,"enabled"))!="true" && JsonDump(JsonObjectGet(p,"enabled"))!="false")return FALSE;
    json skills=JsonObjectGet(p,"skills");int i;
    for(i=0;i<3;i++)
    {
        string name=i==0?"intimidate":(i==1?"persuade":"bluff");
        json row=JsonObjectGet(skills,name);
        if(JsonGetType(JsonObjectGet(row,"dc"))!=JsonGetType(JsonInt(0)) || RWI(row,"dc")<1 || RWI(row,"dc")>60
            || (JsonDump(JsonObjectGet(row,"enabled"))!="true" && JsonDump(JsonObjectGet(row,"enabled"))!="false"))return FALSE;
    }
    if(RWS(cmd,"token")!=GetLocalString(npc,"rw_social_token"))
        SetLocalString(npc,"rw_social_cache","[]");
    SetLocalString(npc,"rw_social_token",RWS(cmd,"token"));
    SetLocalString(npc,"rw_social_policy",JsonDump(p));
    SetLocalInt(npc,"rw_social_lease",GetLocalInt(GetModule(),"rw_tick")+5);
    return TRUE;
}
void RWSocialEmit(object npc,json cmd,json result)
{
    json e=RWBase("social_result",npc);
    e=JsonObjectSet(e,"request",JsonString(RWS(cmd,"request")));
    e=JsonObjectSet(e,"attempt",JsonString(RWS(cmd,"attempt")));
    e=JsonObjectSet(e,"token",JsonString(RWS(cmd,"token")));
    e=JsonObjectSet(e,"skill",JsonObjectGet(result,"skill"));
    e=JsonObjectSet(e,"dc",JsonObjectGet(result,"dc"));
    e=JsonObjectSet(e,"roll",JsonObjectGet(result,"roll"));
    e=JsonObjectSet(e,"modifier",JsonObjectGet(result,"modifier"));
    e=JsonObjectSet(e,"total",JsonObjectGet(result,"total"));
    e=JsonObjectSet(e,"success",JsonObjectGet(result,"success"));RWEmit(e);
}
int RWSocialRoll(object npc,json cmd)
{
    object pc=StringToObject(RWS(cmd,"listener"));
    string skill=RWS(cmd,"skill"), attempt=RWS(cmd,"attempt");int number=RWSocialSkill(skill);
    json p=JsonParse(GetLocalString(npc,"rw_social_policy"));json row=JsonObjectGet(JsonObjectGet(p,"skills"),skill);
    if(!RWSocialOwner(npc,cmd) || RWS(cmd,"token")!=GetLocalString(npc,"rw_social_token")
        || GetLocalInt(GetModule(),"rw_tick")>GetLocalInt(npc,"rw_social_lease")
        || JsonDump(JsonObjectGet(p,"enabled"))!="true" || JsonDump(JsonObjectGet(row,"enabled"))!="true"
        || number<0 || GetStringLength(attempt)!=24
        || !GetIsObjectValid(pc) || !GetIsPC(pc) || GetIsDM(pc) || GetIsDMPossessed(pc) || GetIsDead(pc) || GetIsInCombat(pc)
        || !RWCanHear(pc,npc,RWHearingRange()) || !LineOfSightObject(npc,pc)
        || pc!=GetLocalObject(npc,"rw_enc_chat_pc") || RWS(cmd,"combat_event")==""
        || RWS(cmd,"combat_event")!=GetLocalString(npc,"rw_enc_chat_event"))return FALSE;
    json cache=JsonParse(GetLocalString(npc,"rw_social_cache"));int i;
    string identity=GetPCPublicCDKey(pc)+":"+GetName(pc);
    for(i=0;i<JsonGetLength(cache);i++)
    {
        json previous=JsonArrayGet(cache,i);
        // One roll per player/skill/actor/activation even if the transport retries
        // with a different request ID. Never use a model-generated attempt key.
        if(RWS(previous,"player")==identity && RWS(previous,"skill")==skill)
        {RWSocialEmit(npc,cmd,previous);return TRUE;}
    }
    if(JsonGetLength(cache)>=128)return FALSE;
    int roll=d20(), modifier=GetSkillRank(number,pc), dc=RWI(row,"dc");
    int total=roll+modifier; // Effective skill already includes its ability modifier.
    json result=JsonObject();result=JsonObjectSet(result,"player",JsonString(identity));
    result=JsonObjectSet(result,"skill",JsonString(skill));result=JsonObjectSet(result,"dc",JsonInt(dc));
    result=JsonObjectSet(result,"roll",JsonInt(roll));result=JsonObjectSet(result,"modifier",JsonInt(modifier));
    result=JsonObjectSet(result,"total",JsonInt(total));result=JsonObjectSet(result,"success",JsonInt(total>=dc));
    cache=JsonArrayInsert(cache,result);SetLocalString(npc,"rw_social_cache",JsonDump(cache));
    RWSocialEmit(npc,cmd,result);
    SendMessageToPC(pc,"Role Weaver "+skill+": d20("+IntToString(roll)+") + "+IntToString(modifier)+" = "+IntToString(total)+" vs DC "+IntToString(dc)+(total>=dc?" - success.":" - failed."));
    return TRUE;
}
