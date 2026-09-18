#include "rw_inc"
#include "nwnx_events"
void main()
{
    object old = GetLocalObject(OBJECT_SELF, "rw_possessed");
    if (GetIsObjectValid(old) && GetLocalString(old, "rw_id") != "") RWMode(old, "paused");
    object target = StringToObject(NWNX_Events_GetEventData("TARGET"));
    if (GetIsObjectValid(target) && GetLocalString(target, "rw_id") != "")
    {
        RWMode(target, "dm");
        SetLocalInt(target, "rw_was_possessed", TRUE);
        SetLocalObject(OBJECT_SELF, "rw_possessed", target);
    }
    else DeleteLocalObject(OBJECT_SELF, "rw_possessed");
}
