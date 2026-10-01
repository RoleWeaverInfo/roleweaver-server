// Shared familiar identity and eligibility; no inventory or world placement state.
#include "rw_inc"

// PW integration seam: replace only this lookup/eligibility function when a
// custom companion system does not use the standard familiar association.
object RWCPFind(object owner)
{
    return GetAssociate(ASSOCIATE_TYPE_FAMILIAR,owner);
}
string RWCPOwnerKey(object owner) {return GetPCPublicCDKey(owner)+":"+GetName(owner);}
int RWCPReady(object owner,object familiar)
{
    return GetLocalInt(GetModule(),"rw_cp_enabled") && GetLocalInt(owner,"rw_cp_on")
        && GetLocalString(owner,"rw_cp_login_session")==GetLocalString(GetModule(),"rw_session")
        && GetIsPC(owner) && !GetIsDM(owner) && !GetIsDead(owner)
        && GetIsObjectValid(familiar) && RWCPFind(owner)==familiar && GetMaster(familiar)==owner
        && !GetIsDead(familiar) && !GetIsDMPossessed(familiar) && !GetIsPossessedFamiliar(familiar)
        && !GetIsInCombat(familiar) && !GetIsInCombat(owner) && GetCommandable(familiar)
        && !IsInConversation(owner) && !IsInConversation(familiar)
        && GetArea(familiar)==GetArea(owner);
}
