#include "rw_talk_inc"
void main()
{
    object pc = GetLastSpeaker();
    object npc = OBJECT_SELF;
    if (GetIsPC(pc) && !GetIsDM(pc) && !GetIsDMPossessed(pc)
        && GetLocalString(npc, "rw_id") != "")
    {
        RWEndTalk(pc);
        if (RWCanHear(pc, npc, RWSelectionRange()) && RWBeginTalk(pc, npc))
        {
            SendMessageToPC(pc, "Role Weaver: speaking to " + GetName(npc) + ". Use Talk nearby; type /rw end to finish. Conversation expires after " + IntToString(RWTalkTimeout()) + " seconds without speaking.");
            return;
        }
        SendMessageToPC(pc, "Role Weaver: AI conversation unavailable. Stand within " + IntToString(FloatToInt(RWSelectionRange())) + " metres; the NPC must be in AUTO mode.");
    }
    // Preserve the world's original interaction when AI is unavailable.
    string original = GetLocalString(npc, "rw_old_dialogue");
    if (original != "" && original != "rw_talk") ExecuteScript(original, npc);
}
