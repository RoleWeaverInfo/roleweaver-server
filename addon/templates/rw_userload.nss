// NEW/EMPTY modules: assign to Module Properties > Events > OnModuleLoad.
// EXISTING worlds: keep the current handler; copy these calls into its approved initialization path.
void main()
{
    ExecuteScript("rw_init", GetModule());
    // Optional DM spawning. Keep FALSE if your world owns all NPC creation.
    SetLocalInt(GetModule(), "rw_allow_dm_spawn", FALSE);
    SetLocalInt(GetModule(), "rw_allow_persistent_spawn", FALSE);
}
