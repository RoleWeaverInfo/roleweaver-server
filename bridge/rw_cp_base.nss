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
