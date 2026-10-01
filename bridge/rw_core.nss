// Common bridge definitions; independent of shop and stock helpers.
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

// Perception is bounded and deliberately excludes player names, inventory and secrets.
int RWHasConversation(object npc)
{
    object pc=GetFirstPC();
    while(GetIsObjectValid(pc))
    {
        if(RWCurrentTalk(pc)==npc) return TRUE;
        pc=GetNextPC();
    }
    return FALSE;
}
// Publicly observable state only. Never enumerate inventories, locks, traps,
// hidden identities, resrefs or quest locals. Target metadata is separated by the companion.
string RWVisibleCondition(object o)
{
    if(GetIsDead(o))return "dead";
    int hp=GetCurrentHitPoints(o), maximum=GetMaxHitPoints(o);
    if(maximum>0 && hp*2<maximum)return "badly injured";
    if(hp<maximum)return "injured";
    return "uninjured";
}
string RWVisibleBearing(object npc,object o)
{
    float angle=VectorToAngle(GetPosition(o)-GetPosition(npc))-GetFacing(npc);
    while(angle<0.0)angle+=360.0;
    while(angle>=360.0)angle-=360.0;
    if(angle<22.5 || angle>=337.5)return "ahead";
    if(angle<67.5)return "ahead-left";
    if(angle<112.5)return "left";
    if(angle<157.5)return "behind-left";
    if(angle<202.5)return "behind";
    if(angle<247.5)return "behind-right";
    if(angle<292.5)return "right";
    return "ahead-right";
}
// Ordinary unobstructed creatures may be beyond the engine's local perception
// radius. Hidden/invisible creatures still require actual engine detection.
int RWAreaCreatureVisible(object npc,object target)
{
    if(GetObjectSeen(target,npc))return TRUE;
    if(GetStealthMode(target))return FALSE;
    effect e=GetFirstEffect(target);
    while(GetIsEffectValid(e))
    {
        int t=GetEffectType(e);
        if(t==EFFECT_TYPE_INVISIBILITY || t==EFFECT_TYPE_IMPROVEDINVISIBILITY)return FALSE;
        e=GetNextEffect(target);
    }
    return TRUE;
}
json RWSurroundings(object npc)
{
    int tick=GetLocalInt(GetModule(),"rw_tick");
    // Reuse for at most two bridge ticks; scan cost stays bounded per NPC.
    if(GetLocalInt(npc,"rw_perception_tick")>0 && tick-GetLocalInt(npc,"rw_perception_tick")<2)
        return JsonParse(GetLocalString(npc,"rw_perception_rows"));
    // Forget the previous bounded observer map; target references never grant access
    // to objects that have left this NPC's current visible set.
    json old=JsonParse(GetLocalString(npc,"rw_perception_rows")); int k;
    for(k=0;k<JsonGetLength(old);k++) DeleteLocalObject(npc,"rw_visible_"+RWS(JsonArrayGet(old,k),"ref"));
    json rows=JsonArray(); int scanned=0;
    object o=GetFirstObjectInArea(GetArea(npc));
    // Area-wide sight, with explicit workload/output bounds for crowded worlds.
    while(GetIsObjectValid(o) && scanned<1024 && JsonGetLength(rows)<256)
    {
        scanned++;
        int type=GetObjectType(o);
        if((type==OBJECT_TYPE_CREATURE || type==OBJECT_TYPE_DOOR || type==OBJECT_TYPE_PLACEABLE)
            && o!=npc && GetArea(o)==GetArea(npc) && !GetIsDM(o) && !GetIsDMPossessed(o)
            && LineOfSightObject(npc,o) && (type!=OBJECT_TYPE_CREATURE
                || RWAreaCreatureVisible(npc,o)))
        {
            string kind="placeable";
            if(type==OBJECT_TYPE_CREATURE)kind="character";
            else if(type==OBJECT_TYPE_DOOR)kind="door";
            else if(GetHasInventory(o))kind="container";
            json row=JsonObject();
            if(!GetIsPC(o))
            {
                int serial=GetLocalInt(o,"rw_visible_serial");
                if(!serial) { serial=GetLocalInt(GetModule(),"rw_visible_serial")+1; SetLocalInt(GetModule(),"rw_visible_serial",serial); SetLocalInt(o,"rw_visible_serial",serial); }
                string ref="v"+IntToString(serial);
                SetLocalObject(npc,"rw_visible_"+ref,o);
                row=JsonObjectSet(row,"ref",JsonString(ref));
                // Transport metadata is stripped before model perception. Tags are for the DM's chair allowlist.
                if(type==OBJECT_TYPE_PLACEABLE)row=JsonObjectSet(row,"tag",JsonString(GetTag(o)));
                if(type==OBJECT_TYPE_CREATURE)row=JsonObjectSet(row,"peer",JsonString(GetLocalString(o,"rw_id")));
            }
            row=JsonObjectSet(row,"kind",JsonString(kind));
            row=JsonObjectSet(row,"label",JsonString(GetIsPC(o) ? "Unidentified traveler" : GetStringLeft(GetName(o),80)));
            row=JsonObjectSet(row,"distance",JsonFloat(GetDistanceBetween(npc,o)));
            row=JsonObjectSet(row,"bearing",JsonString(RWVisibleBearing(npc,o)));
            if(type==OBJECT_TYPE_CREATURE)
            {
                row=JsonObjectSet(row,"player",JsonInt(GetIsPC(o)));
                row=JsonObjectSet(row,"condition",JsonString(RWVisibleCondition(o)));
                row=JsonObjectSet(row,"activity",JsonString(GetIsInCombat(o) ? "fighting" : "not fighting"));
                row=JsonObjectSet(row,"attitude",JsonString(GetIsEnemy(o,npc) ? "hostile" : (GetIsFriend(o,npc) ? "friendly" : "neutral")));
                if(!GetIsPC(o) && GetLocalInt(o,"rw_merchant_enabled"))row=JsonObjectSet(row,"merchant",JsonInt(TRUE));
            }
            else
            {
                row=JsonObjectSet(row,"usable",JsonInt(GetUseableFlag(o)));
                if(kind=="door" || kind=="container")row=JsonObjectSet(row,"open",JsonString(GetIsOpen(o) ? "open" : "closed"));
            }
            rows=JsonArrayInsert(rows,row);
        }
        o=GetNextObjectInArea(GetArea(npc));
    }
    SetLocalInt(npc,"rw_perception_truncated",GetIsObjectValid(o));
    SetLocalInt(npc,"rw_perception_tick",tick);
    SetLocalString(npc,"rw_perception_rows",JsonDump(rows));
    return rows;
}
void RWState(object npc)
{
    json v = RWBase("state", npc);
    json peers=JsonArray();
    int j;
    for(j=1;j<=24;j++)
    {
        object peer=GetNearestObject(OBJECT_TYPE_CREATURE,npc,j);
        if(!GetIsObjectValid(peer) || GetDistanceBetween(peer,npc)>6.0) break;
        if(peer!=npc && GetLocalString(peer,"rw_id")!="" && !GetIsPC(peer) && !GetIsDMPossessed(peer)
            && GetArea(peer)==GetArea(npc) && GetObjectSeen(peer,npc) && LineOfSightObject(npc,peer))
            peers=JsonArrayInsert(peers,JsonString(GetLocalString(peer,"rw_id")));
    }
    v=JsonObjectSet(v,"nearby_npcs",peers);
    v=JsonObjectSet(v,"checkins_protocol",JsonInt(1));
    v=JsonObjectSet(v,"scene_speech_protocol",JsonInt(1));
    v=JsonObjectSet(v,"scene_speech_status",JsonString(GetLocalString(npc,"rw_enc_status")));
    v=JsonObjectSet(v,"retreat_protocol",JsonInt(1));
    v=JsonObjectSet(v,"encounter_protocol",JsonInt(7));
    v=JsonObjectSet(v,"live_owner",JsonString(GetLocalString(npc,"rw_live_owner")));
    v=JsonObjectSet(v,"interaction_protocol",JsonInt(1));
    v=JsonObjectSet(v,"interaction_revision",JsonString(GetLocalString(npc,"rw_interaction_revision")));
    v=JsonObjectSet(v,"npc_combat_target",JsonString(GetLocalInt(npc,"rw_combat_target_npc") ? GetLocalString(GetLocalObject(npc,"rw_combat_target"),"rw_id") : ""));
    if(GetLocalInt(npc,"rw_combat_active"))
    {
        v=JsonObjectSet(v,"combat_encounter",JsonString(GetLocalString(npc,"rw_combat_id")));
        v=JsonObjectSet(v,"combat_token",JsonString(GetLocalString(npc,"rw_combat_token")));
        v=JsonObjectSet(v,"combat_phase",JsonString(GetLocalString(npc,"rw_combat_phase")));
    }
    v=JsonObjectSet(v,"awareness_protocol",JsonInt(1));
    v=JsonObjectSet(v,"village_protocol",JsonInt(1));
    v=JsonObjectSet(v,"conversation_active",JsonInt(RWHasConversation(npc)));
    v=JsonObjectSet(v,"surroundings",RWSurroundings(npc));
    v=JsonObjectSet(v,"perception_protocol",JsonInt(3));
    v=JsonObjectSet(v,"nearby_protocol",JsonInt(1));
    v=JsonObjectSet(v,"follow_protocol",JsonInt(1));
    v=JsonObjectSet(v,"inventory_protocol",JsonInt(GetLocalString(npc,"rw_inventory_revision")!="" ? 1 : 0));
    v=JsonObjectSet(v,"inventory_revision",JsonString(GetLocalString(npc,"rw_inventory_revision")));
    v=JsonObjectSet(v,"inventory",JsonParse(GetLocalString(npc,"rw_inventory_snapshot")));
    v=JsonObjectSet(v,"perception_truncated",JsonInt(GetLocalInt(npc,"rw_perception_truncated")));
    v=JsonObjectSet(v,"perception_tick",JsonInt(GetLocalInt(npc,"rw_perception_tick")));
    v=JsonObjectSet(v,"self_condition",JsonString(RWVisibleCondition(npc)));
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
    v=JsonObjectSet(v,"combat",JsonInt(!GetIsDead(npc) && GetIsInCombat(npc)));
    v=JsonObjectSet(v,"action_request",JsonString(GetLocalString(npc,"rw_action_request")));
    v=JsonObjectSet(v,"action_status",JsonString(GetLocalString(npc,"rw_action_status")));
    RWEmit(v);
}

// Undo only the movement lock installed by encounter withdrawal.
void RWCombatRelease(object npc)
{
    if(GetLocalInt(npc,"rw_combat_target_npc") && !GetIsDMPossessed(npc))AssignCommand(npc,ClearAllActions(TRUE));
    DeleteLocalInt(npc,"rw_combat_target_npc");
    if(GetLocalInt(npc,"rw_combat_locked"))
    {
        SetCommandable(GetLocalInt(npc,"rw_combat_commandable"),npc);
        if(!GetIsDMPossessed(npc) && !GetIsDead(npc))AssignCommand(npc,ClearAllActions(TRUE));
        DeleteLocalInt(npc,"rw_combat_locked");
    }
    DeleteLocalInt(npc,"rw_combat_active");
}
void RWMode(object npc, string mode)
{
    RWCombatRelease(npc);
    if(GetLocalInt(npc,"rw_live_staged"))
    {
        SetCommandable(GetLocalInt(npc,"rw_live_commandable"),npc);
        DeleteLocalInt(npc,"rw_live_staged");
    }
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
