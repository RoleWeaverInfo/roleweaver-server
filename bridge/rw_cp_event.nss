// Invalidate pending dialogue before ownership or possession changes.
#include "rw_companion"
#include "nwnx_events"
void main()
{
    object owner=OBJECT_SELF,familiar=RWCPFind(owner);
    // Satchel contents already belong to the saved character. Lifecycle hooks
    // cancel work; they never recreate or move a second copy of possessions.
    RWCPVCancel(familiar,"Familiar control or presence changed.",FALSE);
    RWCPICancel(familiar,"Familiar control or presence changed.",FALSE);
    RWCPHearClear(familiar);
    RWCPEndTalk(owner);RWCPInvalidate(owner);
    if(NWNX_Events_GetCurrentEvent()=="NWNX_ON_CLIENT_DISCONNECT_BEFORE")
    {
        // Save only outstanding inventory changes while the player still
        // exists. Dismissal/possession/associate changes do not change cargo.
        RWCPSFlush(owner);
        DeleteLocalInt(GetModule(),RWCPLoginKey(owner));
        DeleteLocalInt(owner,"rw_cp_on");DeleteLocalString(owner,"rw_cp_login_session");DeleteLocalInt(owner,"rw_cp_save_pending");DeleteLocalInt(owner,"rw_cpp_loaded");DeleteLocalString(owner,"rw_cpp_session");DeleteLocalString(owner,"rw_cpp_pending");
    }
}
