// Staging-only native test: run once with the two example NPCs present.
#include "rw_chat_inc"
void main()
{
    object m = GetModule();
    object mira = RWFind("mira");
    object orren = RWFind("orren");
    object probe = CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",Location(GetArea(mira),Vector(26.7,14.0,0.0),0.0));
    int passed = 0;
    if (GetIsObjectValid(probe) && GetIsObjectValid(mira) && GetIsObjectValid(orren))
    {
        if (RWChatTarget(probe,"Hello") == mira) passed++;
        if (RWChatTarget(probe,"Mira: Hello") == mira) passed++;
        if (RWChatTarget(probe,"orren: Hello") == orren) passed++;
        if (!GetIsObjectValid(RWChatTarget(probe,"Unknown: Hello"))) passed++;
        // Paused nearest NPC remains the recipient; never redirect to another.
        if (GetLocalString(mira,"rw_mode") == "paused" && RWChatTarget(probe,"Hello") == mira) passed++;
        string oldName = GetName(orren);
        SetName(orren,"Mira");
        if (!GetIsObjectValid(RWChatTarget(probe,"Mira: Hello"))) passed++;
        if (RWChatTarget(probe,"orren: Hello") == orren) passed++;
        SetName(orren,oldName);
    }
    WriteTimestampedLogEntry("RW_ROUTING_TEST: " + IntToString(passed) + "/7 passed");
    if (GetIsObjectValid(probe)) DestroyObject(probe);
}
