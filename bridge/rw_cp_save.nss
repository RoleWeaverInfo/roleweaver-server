// Also save changes made by the player through the native bag inventory UI.
#include "rw_cp_pack"
#include "nwnx_events"
void main()
{
    object pack=OBJECT_SELF,owner=GetItemPossessor(pack);
    if(GetLocalInt(pack,"rw_cp_satchel")==1 && GetIsPC(owner) && RWCPIPackOwned(owner,pack))
        RWCPISave(owner); // Shared queue also absorbs explicit transfer requests.
}
