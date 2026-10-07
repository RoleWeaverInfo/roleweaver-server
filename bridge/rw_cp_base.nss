// Shared familiar identity and eligibility; no inventory or world placement state.
#include "rw_inc"

// PW integration seam: replace only this lookup/eligibility function when a
// custom companion system does not use the standard familiar association.
object RWCPFind(object owner)
{
    return GetAssociate(ASSOCIATE_TYPE_FAMILIAR,owner);
}
string RWCPOwnerKey(object owner) {return GetPCPublicCDKey(owner)+":"+GetName(owner);}
string RWCPSettingsIdentity(object owner)
{return RWWorld()+"|"+RWCPOwnerKey(owner)+"|familiar:"+IntToString(GetFamiliarCreatureType(owner));}
// A module-local marker cannot be restored from an exported character. Apply
// the default once per login, never on every heartbeat or familiar resummon.
string RWCPLoginKey(object owner) {return "rw_cp_login_"+ObjectToString(owner);}
void RWCPSetEnabled(object owner,int enabled)
{
    SetLocalInt(GetModule(),RWCPLoginKey(owner),TRUE);
    SetLocalInt(owner,"rw_cp_on",enabled);
    SetLocalString(owner,"rw_cp_login_session",GetLocalString(GetModule(),"rw_session"));
}
void RWCPInitialize(object owner)
{
    object m=GetModule();
    if(!GetIsPC(owner) || GetIsDM(owner) || GetIsDMPossessed(owner) || GetIsPossessedFamiliar(owner)
        || !GetLocalInt(m,"rw_cp_enabled") || GetLocalString(m,"rw_session")==""
        || GetLocalInt(m,RWCPLoginKey(owner)))return;
    RWCPSetEnabled(owner,TRUE);
}
int RWCPPreferencesReady(object owner)
{
    return GetLocalInt(owner,"rw_cpp_loaded")
        && GetLocalString(owner,"rw_cpp_identity")==RWCPSettingsIdentity(owner)
        && GetLocalString(owner,"rw_cpp_session")==GetLocalString(GetModule(),"rw_session")
        && GetLocalString(owner,"rw_cpp_generation")==GetLocalString(GetModule(),"rw_cpp_generation");
}
int RWCPReady(object owner,object familiar)
{
    return GetLocalInt(GetModule(),"rw_cp_enabled") && GetLocalInt(owner,"rw_cp_on")
        && GetLocalString(owner,"rw_cp_login_session")==GetLocalString(GetModule(),"rw_session")
        && RWCPPreferencesReady(owner)
        && GetIsPC(owner) && !GetIsDM(owner) && !GetIsDead(owner)
        && GetIsObjectValid(familiar) && RWCPFind(owner)==familiar && GetMaster(familiar)==owner
        && !GetIsDead(familiar) && !GetIsDMPossessed(familiar) && !GetIsPossessedFamiliar(familiar)
        && !GetIsInCombat(familiar) && !GetIsInCombat(owner) && GetCommandable(familiar)
        && !IsInConversation(owner) && !IsInConversation(familiar)
        && GetArea(familiar)==GetArea(owner);
}

json RWCPEvent(string kind,object owner,object familiar)
{
    json e=RWBase(kind,OBJECT_INVALID);
    e=JsonObjectSet(e,"owner",JsonString(RWCPOwnerKey(owner)));
    e=JsonObjectSet(e,"object",JsonString(ObjectToString(familiar)));
    e=JsonObjectSet(e,"name",JsonString(GetName(familiar)));
    e=JsonObjectSet(e,"creature",JsonString("familiar:"+IntToString(GetFamiliarCreatureType(owner))));
    e=JsonObjectSet(e,"species",JsonString(GetResRef(familiar)));
    e=JsonObjectSet(e,"token",JsonString(GetLocalString(owner,"rw_cp_token")));
    e=JsonObjectSet(e,"sequence",JsonInt(GetLocalInt(owner,"rw_cp_sequence")));
    e=JsonObjectSet(e,"opted_in",JsonInt(GetLocalInt(owner,"rw_cp_on")));
    return JsonObjectSet(e,"active",JsonInt(RWCPReady(owner,familiar)));
}
