// Defaults preserve the tested behavior until the companion synchronizes settings.
int RWConversationValue(string key, int fallback)
{
    if (!GetLocalInt(GetModule(), "rw_talk_configured")) return fallback;
    return GetLocalInt(GetModule(), "rw_talk_" + key);
}
float RWSelectionRange() { return IntToFloat(RWConversationValue("selection_range", 3)); }
float RWCloseRange() { return IntToFloat(RWConversationValue("close_range", 6)); }
float RWHearingRange() { return IntToFloat(RWConversationValue("hearing_range", 10)); }
int RWTalkTimeout() { return RWConversationValue("timeout", 180); }
int RWRequireSight() { return RWConversationValue("line_of_sight", TRUE); }
int RWDirectAddress() { return RWConversationValue("direct_address", TRUE); }
int RWFollowHearing() { return RWConversationValue("follow_hearing", TRUE); }
json RWConversationPolicy()
{
    json p = JsonObject();
    p = JsonObjectSet(p, "selection_range", JsonInt(FloatToInt(RWSelectionRange())));
    p = JsonObjectSet(p, "follow_hearing", JsonInt(RWFollowHearing()));
    p = JsonObjectSet(p, "close_range", JsonInt(FloatToInt(RWCloseRange())));
    p = JsonObjectSet(p, "hearing_range", JsonInt(FloatToInt(RWHearingRange())));
    p = JsonObjectSet(p, "timeout", JsonInt(RWTalkTimeout()));
    p = JsonObjectSet(p, "line_of_sight", JsonInt(RWRequireSight()));
    return JsonObjectSet(p, "direct_address", JsonInt(RWDirectAddress()));
}
int RWConversationInteger(json p, string key)
{
    return JsonGetType(JsonObjectGet(p, key)) == JsonGetType(JsonInt(0));
}
int RWApplyConversationPolicy(json p, string revision)
{
    if (GetStringLength(revision) != 24 || !RWConversationInteger(p,"close_range")
        || !RWConversationInteger(p,"selection_range") || !RWConversationInteger(p,"follow_hearing")
        || !RWConversationInteger(p,"hearing_range") || !RWConversationInteger(p,"timeout")
        || !RWConversationInteger(p,"line_of_sight") || !RWConversationInteger(p,"direct_address")) return FALSE;
    int selection = JsonGetInt(JsonObjectGet(p,"selection_range"));
    int follow = JsonGetInt(JsonObjectGet(p,"follow_hearing"));
    int close = JsonGetInt(JsonObjectGet(p,"close_range"));
    int hearing = JsonGetInt(JsonObjectGet(p,"hearing_range"));
    int timeout = JsonGetInt(JsonObjectGet(p,"timeout"));
    int sight = JsonGetInt(JsonObjectGet(p,"line_of_sight"));
    int address = JsonGetInt(JsonObjectGet(p,"direct_address"));
    if (selection < 1 || selection > close || follow < 0 || follow > 1 || hearing > 20 || close > hearing || timeout < 15 || timeout > 300
        || sight < 0 || sight > 1 || address < 0 || address > 1) return FALSE;
    object m = GetModule();
    if (GetLocalString(m,"rw_talk_revision") == revision) return TRUE;
    SetLocalInt(m,"rw_talk_selection_range",selection);
    SetLocalInt(m,"rw_talk_follow_hearing",follow);
    SetLocalInt(m,"rw_talk_close_range",close);
    SetLocalInt(m,"rw_talk_hearing_range",hearing);
    SetLocalInt(m,"rw_talk_timeout",timeout);
    SetLocalInt(m,"rw_talk_line_of_sight",sight);
    SetLocalInt(m,"rw_talk_direct_address",address);
    SetLocalInt(m,"rw_talk_configured",TRUE);
    SetLocalString(m,"rw_talk_revision",revision);
    return TRUE;
}

// A conversation belongs to one player, never to everyone near an NPC.
void RWEndTalk(object pc)
{
    DeleteLocalObject(pc, "rw_talk_target");
    DeleteLocalInt(pc, "rw_talk_until");
    DeleteLocalString(pc, "rw_talk_session");
    DeleteLocalInt(pc, "rw_talk_epoch");
    DeleteLocalString(pc, "rw_talk_policy");
    DeleteLocalInt(pc, "rw_talk_follow_until");
}

int RWCanHear(object pc, object npc, float range)
{
    return GetIsObjectValid(npc) && !GetIsDead(npc)
        && GetLocalString(npc, "rw_id") != ""
        && GetLocalObject(GetModule(), "rw_npc_" + GetLocalString(npc, "rw_id")) == npc
        && GetArea(pc) == GetArea(npc) && GetDistanceBetween(pc, npc) <= range
        && (!RWRequireSight() || LineOfSightObject(pc, npc));
}

int RWBeginTalk(object pc, object npc)
{
    int followUntil=0;
    if (GetLocalObject(pc,"rw_talk_target")==npc) followUntil=GetLocalInt(pc,"rw_talk_follow_until");
    RWEndTalk(pc);
    if (!RWCanHear(pc, npc, RWHearingRange()) || GetIsDMPossessed(npc)
        || GetLocalString(npc, "rw_mode") != "auto") return FALSE;
    SetLocalObject(pc, "rw_talk_target", npc);
    SetLocalInt(pc,"rw_talk_follow_until",followUntil);
    SetLocalString(pc, "rw_talk_policy", GetLocalString(GetModule(), "rw_talk_revision"));
    SetLocalInt(pc, "rw_talk_until", GetLocalInt(GetModule(), "rw_tick") + RWTalkTimeout());
    SetLocalInt(pc, "rw_talk_epoch", GetLocalInt(npc, "rw_epoch"));
    SetLocalString(pc, "rw_talk_session", GetLocalString(GetModule(), "rw_session"));
    return TRUE;
}

// Keep the selection while a player catches up, but stationary follow-up speech uses close range.
float RWRetainRange()
{
    if (RWFollowHearing()) return RWHearingRange();
    return RWCloseRange();
}
float RWFollowupRange(object pc, object npc)
{
    if (RWFollowHearing() && (GetCurrentAction(npc)==ACTION_MOVETOPOINT
        || ((GetLocalString(npc,"rw_action_status")=="running" || GetLocalString(npc,"rw_action_status")=="waiting for player") && (GetLocalString(npc,"rw_action_kind")=="walk" || GetLocalString(npc,"rw_action_kind")=="lead" || GetLocalString(npc,"rw_action_kind")=="home"))))
        SetLocalInt(pc,"rw_talk_follow_until",GetLocalInt(GetModule(),"rw_tick")+10);
    if (RWFollowHearing() && GetLocalInt(pc,"rw_talk_follow_until")>GetLocalInt(GetModule(),"rw_tick")) return RWHearingRange();
    return RWCloseRange();
}
object RWCurrentTalk(object pc)
{
    object npc = GetLocalObject(pc, "rw_talk_target");
    if (!RWCanHear(pc, npc, RWRetainRange()) || GetIsDMPossessed(npc)
        || GetLocalString(npc, "rw_mode") != "auto"
        || GetLocalInt(pc, "rw_talk_until") <= GetLocalInt(GetModule(), "rw_tick")
        || GetLocalInt(pc, "rw_talk_epoch") != GetLocalInt(npc, "rw_epoch")
        || GetLocalString(pc, "rw_talk_policy") != GetLocalString(GetModule(), "rw_talk_revision")
        || GetLocalString(pc, "rw_talk_session") != GetLocalString(GetModule(), "rw_session"))
    { RWEndTalk(pc); return OBJECT_INVALID; }
    RWFollowupRange(pc,npc);
    return npc;
}

// Install only on explicitly bound creatures; restore on unbind.
void RWInstallTalk(object npc)
{
    string original = GetEventScript(npc, EVENT_SCRIPT_CREATURE_ON_DIALOGUE);
    if (original == "rw_talk") return;
    SetLocalString(npc, "rw_old_dialogue", original);
    SetEventScript(npc, EVENT_SCRIPT_CREATURE_ON_DIALOGUE, "rw_talk");
}
