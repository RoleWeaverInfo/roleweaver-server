// Call from the world's existing spawn/load code, with OBJECT_SELF = creature.
// SetLocalString(npc, "rw_profile", "profile_id"); ExecuteScript("rw_bind", npc);
#include "rw_inc"
void main() { RWBind(OBJECT_SELF, GetLocalString(OBJECT_SELF, "rw_profile"), OBJECT_INVALID); }
