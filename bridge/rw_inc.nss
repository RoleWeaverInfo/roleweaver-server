#include "rw_creature"
#include "nwnx_core"
#include "nwnx_redis"
#include "rw_settings"
#include "rw_talk_inc"

// Only these namespaced keys are used. Redis remains on the local VM.
string RWKey(string suffix) { return RW_REDIS_PREFIX + ":" + suffix; }
string RWWorld() { return RW_WORLD; }
string RWS(json value, string key) { return JsonGetString(JsonObjectGet(value, key)); }
int RWI(json value, string key) { return JsonGetInt(JsonObjectGet(value, key)); }

void RWEmit(json value)
{
    NWNX_Redis_GetResultAsInt(NWNX_Redis_RPUSH(RWKey("events"), JsonDump(value)));
    NWNX_Redis_GetResultAsInt(NWNX_Redis_LTRIM(RWKey("events"), -256, -1));
    NWNX_Redis_GetResultAsInt(NWNX_Redis_EXPIRE(RWKey("events"), 15));
}

json RWBase(string kind, object npc)
{
    object m = GetModule();
    json v = JsonObject();
    v = JsonObjectSet(v, "kind", JsonString(kind));
    v = JsonObjectSet(v, "npc", JsonString(GetLocalString(npc, "rw_id")));
    v = JsonObjectSet(v, "session", JsonString(GetLocalString(m, "rw_session")));
    v = JsonObjectSet(v, "epoch", JsonInt(GetLocalInt(npc, "rw_epoch")));
    v = JsonObjectSet(v, "tick", JsonInt(GetLocalInt(m, "rw_tick")));
    v = JsonObjectSet(v, "world", JsonString(RWWorld()));
    v = JsonObjectSet(v, "owns_placements", JsonInt(RW_OWNS_PLACEMENTS || GetLocalInt(m, "rw_allow_persistent_spawn")));
    return v;
}

void RWState(object npc)
{
    json v = RWBase("state", npc);
    v = JsonObjectSet(v, "object", JsonString(ObjectToString(npc)));
    v = JsonObjectSet(v, "mode", JsonString(GetLocalString(npc, "rw_mode")));
    v = JsonObjectSet(v, "source", JsonString(GetLocalString(npc, "rw_source")));
    v = JsonObjectSet(v, "area", JsonString(GetName(GetArea(npc))));
    v = JsonObjectSet(v, "area_resref", JsonString(GetResRef(GetArea(npc))));
    v = JsonObjectSet(v, "area_tag", JsonString(GetTag(GetArea(npc))));
    v = JsonObjectSet(v, "dead", JsonInt(GetIsDead(npc)));
    v = JsonObjectSet(v, "possessed", JsonInt(GetIsDMPossessed(npc)));
    vector pos = GetPosition(npc);
    v = JsonObjectSet(v, "x", JsonFloat(pos.x));
    v = JsonObjectSet(v, "y", JsonFloat(pos.y));
    int nearby = 0;
    object pc = GetFirstPC();
    while (GetIsObjectValid(pc))
    {
        if (!GetIsDM(pc) && !GetIsDMPossessed(pc) && GetArea(pc) == GetArea(npc)
            && GetDistanceBetween(pc, npc) <= RWHearingRange() && (!RWRequireSight() || LineOfSightObject(pc, npc))) nearby++;
        pc = GetNextPC();
    }
    v = JsonObjectSet(v, "nearby_players", JsonInt(nearby));
    v = JsonObjectSet(v,"appearance",JsonInt(GetAppearanceType(npc)));
    v = JsonObjectSet(v,"level",JsonInt(GetHitDice(npc)));
    v = JsonObjectSet(v,"npc_class",JsonInt(GetClassByPosition(1,npc)));
    v=JsonObjectSet(v,"merchant_enabled",JsonInt(GetLocalInt(npc,"rw_merchant_enabled")));
    v=JsonObjectSet(v,"merchant_revision",JsonString(GetLocalString(npc,"rw_merchant_revision")));
    v=JsonObjectSet(v,"combat",JsonInt(GetIsInCombat(npc)));
    v=JsonObjectSet(v,"action_request",JsonString(GetLocalString(npc,"rw_action_request")));
    v=JsonObjectSet(v,"action_status",JsonString(GetLocalString(npc,"rw_action_status")));
    RWEmit(v);
}

void RWMode(object npc, string mode)
{
    if ((GetLocalString(npc,"rw_action_status")=="running" || GetLocalString(npc,"rw_action_status")=="waiting for player"))
    {
        SetLocalString(npc,"rw_action_status","interrupted");
        if (!GetIsDMPossessed(npc)) AssignCommand(npc,ClearAllActions(TRUE));
    }
    SetLocalInt(npc, "rw_epoch", GetLocalInt(npc, "rw_epoch") + 1);
    SetLocalString(npc, "rw_mode", mode);
    // Speech is sent synchronously only after epoch/possession validation.
    RWState(npc);
}

object RWFind(string id)
{
    return GetLocalObject(GetModule(), "rw_npc_" + id);
}

int RWValidID(string id)
{
    int i, n = GetStringLength(id);
    if (n < 1 || n > 24) return FALSE;
    if (FindSubString("abcdefghijklmnopqrstuvwxyz", GetSubString(id, 0, 1)) < 0) return FALSE;
    for (i = 0; i < n; i++)
        if (FindSubString("abcdefghijklmnopqrstuvwxyz0123456789_", GetSubString(id, i, 1)) < 0) return FALSE;
    return TRUE;
}

void RWPlacement(object npc)
{
    if (GetLocalString(npc, "rw_source") == "dm_temporary") return;
    if (!RW_OWNS_PLACEMENTS && GetLocalString(npc, "rw_source") != "dm_persistent") return;
    if (GetLocalInt(GetModule(), "rw_restoring")) return;
    object area = GetArea(npc);
    if (!GetIsObjectValid(area)) return;
    vector p = GetPosition(npc);
    json v = RWBase("placement", npc);
    v = JsonObjectSet(v, "area", JsonString(GetResRef(area)));
    v = JsonObjectSet(v, "area_tag", JsonString(GetTag(area)));
    v = JsonObjectSet(v, "tag", JsonString(GetTag(npc)));
    v = JsonObjectSet(v, "resref", JsonString(GetResRef(npc)));
    v = JsonObjectSet(v, "name", JsonString(GetName(npc)));
    string source = GetLocalString(npc, "rw_source");
    if (source == "") source = "bind";
    v = JsonObjectSet(v, "source", JsonString(source));
    v = JsonObjectSet(v, "x", JsonFloat(p.x));
    v = JsonObjectSet(v, "y", JsonFloat(p.y));
    v = JsonObjectSet(v, "z", JsonFloat(p.z));
    v = JsonObjectSet(v, "facing", JsonFloat(GetFacing(npc)));
    v = JsonObjectSet(v, "dead", JsonInt(GetIsDead(npc)));
    string build = GetLocalString(npc,"rw_creature");
    if(build!="") v=JsonObjectSet(v,"creature",JsonParse(build));
    RWEmit(v);
}

int RWHasSlot()
{
    object m = GetModule();
    int count = GetLocalInt(m, "rw_count");
    if (count < 32) return TRUE;
    int i;
    for (i = 0; i < count; i++)
        if (!GetIsObjectValid(GetLocalObject(m, "rw_slot_" + IntToString(i)))) return TRUE;
    return FALSE;
}

void RWBind(object npc, string id, object dm)
{
    object m = GetModule();
    if (!RWValidID(id) || !GetIsObjectValid(npc) || GetObjectType(npc) != OBJECT_TYPE_CREATURE || GetIsPC(npc) || GetIsDM(npc) || GetIsDMPossessed(npc))
    { SendMessageToPC(dm, "Role Weaver: invalid ID or creature."); return; }
    if (GetIsObjectValid(RWFind(id)) || GetLocalString(npc, "rw_id") != "")
    { SendMessageToPC(dm, "Role Weaver: ID or creature is already bound."); return; }
    int count = GetLocalInt(m, "rw_count");
    int slot = 0;
    while (slot < count && GetIsObjectValid(GetLocalObject(m, "rw_slot_" + IntToString(slot)))) slot++;
    if (slot >= 32) { SendMessageToPC(dm, "Role Weaver: 32 NPC limit reached."); return; }
    SetLocalString(npc, "rw_id", id);
    RWInstallTalk(npc);
    SetLocalObject(m, "rw_npc_" + id, npc);
    SetLocalObject(m, "rw_slot_" + IntToString(slot), npc);
    if (slot == count) SetLocalInt(m, "rw_count", count + 1);
    RWMode(npc, "paused");
    RWPlacement(npc);
    SendMessageToPC(dm, "Role Weaver: bound " + id + " to " + GetName(npc) + ". Resume from the dashboard when ready.");
}

int RWRestore(json cmd)
{
    if (!RW_OWNS_PLACEMENTS && !(GetLocalInt(GetModule(), "rw_allow_persistent_spawn") && RWS(cmd, "source") == "dm_persistent")) return FALSE;
    object m = GetModule();
    string id = RWS(cmd, "npc");
    SetLocalString(m, "rw_restore_error", "Invalid placement");
    if (RWS(cmd, "world") != RWWorld() || !RWValidID(id)) return FALSE;
    object npc = RWFind(id);
    // Retried restore commands must never duplicate, move, or seize an existing NPC.
    if (GetIsObjectValid(npc)) { RWState(npc); RWPlacement(npc); return TRUE; }
    if (!RWHasSlot()) { SetLocalString(m, "rw_restore_error", "32 NPC limit reached"); return FALSE; }
    object area = GetFirstArea();
    object target = OBJECT_INVALID;
    int matches = 0;
    while (GetIsObjectValid(area))
    {
        if (GetResRef(area) == RWS(cmd, "area") && GetTag(area) == RWS(cmd, "area_tag")) { target = area; matches++; }
        area = GetNextArea();
    }
    if (matches != 1) { SetLocalString(m, "rw_restore_error", "Saved area missing or ambiguous"); return FALSE; }
    vector p = Vector(JsonGetFloat(JsonObjectGet(cmd, "x")), JsonGetFloat(JsonObjectGet(cmd, "y")), JsonGetFloat(JsonObjectGet(cmd, "z")));
    location loc = Location(target, p, JsonGetFloat(JsonObjectGet(cmd, "facing")));
    string source = RWS(cmd, "source");
    if (source == "bind")
    {
        string tag = RWS(cmd, "tag");
        if (tag == "") { SetLocalString(m, "rw_restore_error", "Existing creature needs a unique tag"); return FALSE; }
        matches = 0;
        int i = 0;
        object candidate = GetObjectByTag(tag, i);
        while (GetIsObjectValid(candidate))
        {
            if (GetObjectType(candidate) == OBJECT_TYPE_CREATURE && GetResRef(candidate) == RWS(cmd, "resref")) { npc = candidate; matches++; }
            i++; candidate = GetObjectByTag(tag, i);
        }
        if (matches != 1) { SetLocalString(m, "rw_restore_error", "Existing creature missing or tag ambiguous"); return FALSE; }
        if (GetIsPC(npc) || GetIsDM(npc) || GetIsDMPossessed(npc) || GetLocalString(npc, "rw_id") != "") return FALSE;
    }
    else if (source == "spawn" || source == "dm_persistent")
    {
        if (JsonGetType(JsonObjectGet(cmd,"creature"))==JSON_TYPE_OBJECT) npc=RWCreateCreature(JsonObjectGet(cmd,"creature"),loc);
        else npc = CreateObject(OBJECT_TYPE_CREATURE, RWS(cmd, "resref"), loc);
        if (!GetIsObjectValid(npc)) { SetLocalString(m, "rw_restore_error", "Creature blueprint unavailable"); return FALSE; }
        SetTag(npc, RWS(cmd, "tag"));
    }
    else return FALSE;
    SetLocalString(npc, "rw_source", source);
    SetName(npc, RWS(cmd, "name"));
    SetLocalInt(m, "rw_restoring", TRUE);
    RWBind(npc, id, OBJECT_INVALID);
    DeleteLocalInt(m, "rw_restoring");
    if (source == "bind") AssignCommand(npc, JumpToLocation(loc));
    DelayCommand(0.5, RWPlacement(npc));
    return GetIsObjectValid(RWFind(id));
}

#include "rw_merchant"
