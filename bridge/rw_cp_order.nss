// Stock NWN familiar adapter. Modified PWs may replace this script via the module
// local rw_companion_adapter. Never change heartbeat/combat/conversation scripts.
#include "nw_i0_generic"
void main()
{
    object owner=GetMaster();string order=GetLocalString(OBJECT_SELF,"rw_cp_order");
    if(!GetIsPC(owner) || GetAssociate(ASSOCIATE_TYPE_FAMILIAR,owner)!=OBJECT_SELF
        || GetIsDead(OBJECT_SELF) || GetIsPossessedFamiliar(OBJECT_SELF)
        || GetIsDMPossessed(OBJECT_SELF) || GetIsInCombat(OBJECT_SELF) || !GetCommandable())return;
    if(order=="companion:task_move" || order=="companion:task_continue" || order=="companion:task_end")
    {
        if(order=="companion:task_move")SetLocalInt(OBJECT_SELF,"rw_cp_pre_task_stay",GetAssociateState(NW_ASC_MODE_STAND_GROUND));
        ClearAllActions(TRUE);ResetHenchmenState();
        int stay=order=="companion:task_end"?GetLocalInt(OBJECT_SELF,"rw_cp_pre_task_stay"):TRUE;
        SetAssociateState(NW_ASC_MODE_STAND_GROUND,stay);SetAssociateState(NW_ASC_MODE_DEFEND_MASTER,FALSE);
        if(order=="companion:task_end")
        {if(!stay)ActionForceFollowObject(owner,3.0);}
        else
        {
            object target=GetLocalObject(OBJECT_SELF,"rw_cp_order_target");
            if(!GetIsObjectValid(target) || GetArea(target)!=GetArea(OBJECT_SELF))return;
            ActionMoveToObject(target,FALSE,1.5);
        }
        SetLocalInt(OBJECT_SELF,"rw_cp_order_ok",TRUE);return;
    }
    if(order!="companion:follow" && order!="companion:stay")return;
    ClearAllActions(TRUE);
    ResetHenchmenState();
    SetAssociateState(NW_ASC_MODE_STAND_GROUND,order=="companion:stay");
    SetAssociateState(NW_ASC_MODE_DEFEND_MASTER,FALSE);
    if(order=="companion:follow")ActionForceFollowObject(owner,3.0);
    SetLocalInt(OBJECT_SELF,"rw_cp_order_ok",TRUE);
}
