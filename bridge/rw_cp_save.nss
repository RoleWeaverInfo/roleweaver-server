// Also save changes made by the player through the native bag inventory UI.
#include "rw_cp_pack"
#include "nwnx_events"
void SaveOwner(object owner)
{
    DeleteLocalInt(owner,"rw_cp_save_pending");
    if(GetIsPC(owner))ExportSingleCharacter(owner);
}
void main()
{
    object pack=OBJECT_SELF,owner=GetItemPossessor(pack);
    if(GetLocalInt(pack,"rw_cp_satchel")==1 && GetIsPC(owner) && RWCPIPackOwned(owner,pack)
        && (!GetLocalInt(owner,"rw_cp_save_pending")
            || GetLocalString(owner,"rw_cp_save_session")!=GetLocalString(GetModule(),"rw_session")))
    {
        // The native inventory event fires inside a move. Save once after the
        // move completes, grouping multiple stack updates from that operation.
        SetLocalInt(owner,"rw_cp_save_pending",TRUE);
        SetLocalString(owner,"rw_cp_save_session",GetLocalString(GetModule(),"rw_session"));
        AssignCommand(owner,DelayCommand(0.25,SaveOwner(owner)));
    }
}
