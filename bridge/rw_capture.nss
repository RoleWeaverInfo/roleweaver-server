// One-time migration helper: save bindings from the preview before restarting.
#include "rw_inc"
void main()
{
    object m = GetModule();
    int i;
    for (i = 0; i < GetLocalInt(m, "rw_count"); i++)
    {
        object npc = GetLocalObject(m, "rw_slot_" + IntToString(i));
        if (GetIsObjectValid(npc))
        {
            if (GetLocalString(npc, "rw_id") == "mira" && GetTag(npc) == "rw_mira") SetLocalString(npc, "rw_source", "spawn");
            RWPlacement(npc);
        }
    }
    WriteTimestampedLogEntry("ROLEWEAVER: placement migration capture completed.");
}
