// Detach before the world despawns/reuses a creature. Never destroys the creature.
#include "rw_inc"
void main()
{
    object m = GetModule();
    string id = GetLocalString(OBJECT_SELF, "rw_id");
    if (id == "" || RWFind(id) != OBJECT_SELF) return;
    RWMode(OBJECT_SELF, "paused");
    RWShopDetach(OBJECT_SELF);
    if (GetEventScript(OBJECT_SELF, EVENT_SCRIPT_CREATURE_ON_DIALOGUE) == "rw_talk")
        SetEventScript(OBJECT_SELF, EVENT_SCRIPT_CREATURE_ON_DIALOGUE, GetLocalString(OBJECT_SELF, "rw_old_dialogue"));
    DeleteLocalString(OBJECT_SELF, "rw_old_dialogue");
    DeleteLocalObject(m, "rw_npc_" + id);
    DeleteLocalString(OBJECT_SELF, "rw_id");
    int i;
    for (i = 0; i < GetLocalInt(m, "rw_count"); i++)
        if (GetLocalObject(m, "rw_slot_" + IntToString(i)) == OBJECT_SELF)
            DeleteLocalObject(m, "rw_slot_" + IntToString(i));
}
