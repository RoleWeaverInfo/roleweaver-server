// Example WORLD spawn hook. Install only in the staging test world.
void BindWorldNPC(object area, string id, string name, float x)
{
    object npc = GetObjectByTag("pw_" + id);
    if (!GetIsObjectValid(npc))
    {
        npc = CreateObject(OBJECT_TYPE_CREATURE, "innkeeper", Location(area, Vector(x,14.0,0.0),0.0));
        SetTag(npc, "pw_" + id);
        SetName(npc, name);
    }
    SetLocalString(npc, "rw_profile", id);
    if (GetLocalString(npc, "rw_id") == "") ExecuteScript("rw_bind", npc);
}
void main()
{
    SetLocalInt(GetModule(), "rw_allow_dm_spawn", TRUE);
    SetLocalInt(GetModule(), "rw_allow_persistent_spawn", TRUE);
    object area = GetObjectByTag("starting_area");
    if (!GetIsObjectValid(area)) return;
    BindWorldNPC(area, "mira", "Mira", 27.7);
    BindWorldNPC(area, "orren", "Orren", 31.7);
    WriteTimestampedLogEntry("PW_STAGING: two world-owned NPCs bound; start paused.");
}
