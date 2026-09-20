#include "rw_inc"
#include "nwnx_chat"
#include "rw_actions"
void RWFinishMove(object npc, location destination, string request, int epoch)
{
    int ok = GetIsObjectValid(npc) && !GetIsDMPossessed(npc) && GetLocalInt(npc, "rw_epoch") == epoch
        && GetArea(npc) == GetAreaFromLocation(destination) && GetDistanceBetweenLocations(GetLocation(npc), destination) < 2.0;
    if (ok) RWPlacement(npc);
    json ack = RWBase("ack", npc);
    ack = JsonObjectSet(ack, "request", JsonString(request));
    ack = JsonObjectSet(ack, "ok", JsonInt(ok));
    RWEmit(ack);
}
void main()
{
    object m = GetModule();
    int tick = GetLocalInt(m, "rw_tick") + 1;
    SetLocalInt(m, "rw_tick", tick);
    object participant = GetFirstPC();
    while (GetIsObjectValid(participant))
    {
        RWCurrentTalk(participant);
        participant = GetNextPC();
    }
    json hello = RWBase("hello", OBJECT_INVALID);
    hello = JsonObjectSet(hello,"conversation_protocol",JsonInt(2));
    hello = JsonObjectSet(hello,"conversation",RWConversationPolicy());
    hello = JsonObjectSet(hello,"conversation_revision",JsonString(GetLocalString(m,"rw_talk_revision")));
    hello = JsonObjectSet(hello,"actions_protocol",JsonInt(6));
    RWEmit(hello);
    if (GetLocalInt(m, "rw_allow_dm_spawn"))
    {
        object dm = GetFirstPC();
        while (GetIsObjectValid(dm))
        {
            if (GetIsDM(dm) && !GetIsDMPossessed(dm))
            {
                string token = GetLocalString(dm, "rw_dm_token");
                if (token == "") { token = IntToString(Random(2000000000)) + ObjectToString(dm); SetLocalString(dm, "rw_dm_token", token); }
                json d = RWBase("dm_available", OBJECT_INVALID);
                d = JsonObjectSet(d, "dm", JsonString(ObjectToString(dm)));
                d = JsonObjectSet(d, "token", JsonString(token));
                d = JsonObjectSet(d, "name", JsonString(GetName(dm)));
                RWEmit(d);
            }
            dm = GetNextPC();
        }
    }
    int count = GetLocalInt(m, "rw_count"), i;
    for (i = 0; i < count; i++)
    {
        object npc = GetLocalObject(m, "rw_slot_" + IntToString(i));
        if (GetIsObjectValid(npc))
        {
            // Track actual possession separately from a dashboard DM reservation.
            if (GetIsDMPossessed(npc))
            {
                SetLocalInt(npc, "rw_was_possessed", TRUE);
                if (GetLocalString(npc, "rw_mode") != "dm") RWMode(npc, "dm");
            }
            else if (GetLocalInt(npc, "rw_was_possessed"))
            {
                DeleteLocalInt(npc, "rw_was_possessed");
                RWMode(npc, "paused");
            }
            RWActionTick(npc);
            RWState(npc);
            if (tick % 5 == 0) {RWPlacement(npc);RWShopTick(npc);}
        }
    }
    for (i = 0; i < 16; i++)
    {
        int result = NWNX_Redis_LPOP(RWKey("commands"));
        int resultType = NWNX_Redis_GetResultType(result);
        string raw = NWNX_Redis_GetResultAsString(result);
        if (resultType == NWNX_REDIS_RESULT_NULL || raw == "") break;
        json cmd = JsonParse(raw);
        if (RWS(cmd,"kind") == "conversation_settings")
        {
            if (RWS(cmd,"world") == RWWorld() && RWS(cmd,"session") == GetLocalString(m,"rw_session")
                && RWI(cmd,"expires") >= tick && RWI(cmd,"expires") <= tick + 5)
                RWApplyConversationPolicy(JsonObjectGet(cmd,"settings"), RWS(cmd,"revision"));
            continue;
        }
        if (RWS(cmd,"kind")=="action_capture") { RWCaptureAction(cmd); continue; }
        object npc = RWFind(RWS(cmd, "npc"));
        int ok = FALSE;
        if (RWS(cmd, "kind") == "spawn_dm" && GetLocalInt(m, "rw_allow_dm_spawn")
            && RWS(cmd, "session") == GetLocalString(m, "rw_session") && RWI(cmd, "expires") >= tick && RWI(cmd, "expires") <= tick + 5
            && !GetIsObjectValid(npc) && RWValidID(RWS(cmd, "npc")) && RWHasSlot()
            && (RWS(cmd, "blueprint") == "innkeeper" || RWS(cmd, "blueprint") == "rw_custom")
            && (RWS(cmd, "persistence") == "temporary" || (RWS(cmd, "persistence") == "persistent" && GetLocalInt(m, "rw_allow_persistent_spawn"))))
        {
            object dm = StringToObject(RWS(cmd, "dm"));
            if (GetIsObjectValid(dm) && GetIsDM(dm) && !GetIsDMPossessed(dm) && GetIsObjectValid(GetArea(dm))
                && GetLocalString(dm, "rw_dm_token") == RWS(cmd, "token"))
            {
                if(RWS(cmd,"blueprint")=="rw_custom") npc=RWCreateCreature(JsonObjectGet(cmd,"creature"),GetLocation(dm));
                else npc = CreateObject(OBJECT_TYPE_CREATURE, "innkeeper", GetLocation(dm));
                if (GetIsObjectValid(npc))
                {
                    SetName(npc, RWS(cmd, "name"));
                    SetTag(npc, "rw_temp_" + RWS(cmd, "npc"));
                    if (RWS(cmd, "persistence") == "persistent") SetLocalString(npc, "rw_source", "dm_persistent");
                    else SetLocalString(npc, "rw_source", "dm_temporary");
                    RWBind(npc, RWS(cmd, "npc"), dm);
                    ok = RWFind(RWS(cmd, "npc")) == npc;
                    if (!ok) DestroyObject(npc);
                }
            }
        }
        if (RWS(cmd, "kind") == "restore" && RWS(cmd, "session") == GetLocalString(m, "rw_session") && RWI(cmd, "expires") >= tick && RWI(cmd, "expires") <= tick + 5)
            ok = RWRestore(cmd);
        if (GetIsObjectValid(npc) && RWS(cmd, "session") == GetLocalString(m, "rw_session") && RWI(cmd, "epoch") == GetLocalInt(npc, "rw_epoch") && RWI(cmd, "expires") >= tick && RWI(cmd, "expires") <= tick + 5)
        {
            string kind = RWS(cmd, "kind");
            if (kind=="merchant_setup" && RWS(cmd,"world")==RWWorld() && (RWI(cmd,"enabled")==0 || RWI(cmd,"enabled")==1))
            {if(RWApplyMerchantRules(npc,JsonObjectGet(cmd,"rules"),RWS(cmd,"rules_revision"))){SetLocalInt(npc,"rw_merchant_enabled",RWI(cmd,"enabled"));RWShopTick(npc);ok=TRUE;}}
            if(kind=="merchant_stock_edit" && RWStockEdit(npc,cmd))continue;
            if (kind=="controlled_action") ok=RWStartAction(npc,cmd);
            if (kind=="controlled_stop" && !GetIsDMPossessed(npc)) { RWMode(npc,GetLocalString(npc,"rw_mode")); ok=TRUE; }
            string source = GetLocalString(npc, "rw_source");
            int managed = GetLocalInt(m, "rw_allow_dm_spawn") && (source == "dm_persistent" || source == "dm_temporary");
            if (managed && !GetIsDMPossessed(npc))
            {
                if (kind == "persistence" && (RWS(cmd, "persistence") == "temporary" ||
                    (RWS(cmd, "persistence") == "persistent" && GetLocalInt(m, "rw_allow_persistent_spawn"))))
                {
                    string updatedSource = "dm_temporary";
                    if (RWS(cmd, "persistence") == "persistent") updatedSource = "dm_persistent";
                    SetLocalString(npc, "rw_source", updatedSource);
                    RWMode(npc, "paused"); RWPlacement(npc); ok = TRUE;
                }
                if (kind == "despawn" && (RWS(cmd, "return_mode") == "never" ||
                    (RWS(cmd, "return_mode") == "restart" && source == "dm_persistent")))
                {
                    RWMode(npc, "paused");
                    if (RWS(cmd, "return_mode") == "restart") RWPlacement(npc);
                    ExecuteScript("rw_unbind", npc);
                    DestroyObject(npc); ok = TRUE;
                }
                if (kind == "move_dm" && !GetIsDead(npc))
                {
                    object targetDM = StringToObject(RWS(cmd, "dm"));
                    if (GetIsObjectValid(targetDM) && GetIsDM(targetDM) && !GetIsDMPossessed(targetDM)
                        && GetIsObjectValid(GetArea(targetDM)) && GetLocalString(targetDM, "rw_dm_token") == RWS(cmd, "token"))
                    {
                        location destination = GetLocation(targetDM);
                        RWMode(npc, "paused");
                        AssignCommand(npc, ClearAllActions(TRUE));
                        AssignCommand(npc, JumpToLocation(destination));
                        DelayCommand(0.5, RWFinishMove(npc, destination, RWS(cmd, "request"), GetLocalInt(npc, "rw_epoch")));
                        continue;
                    }
                }
            }
            if (kind == "delete")
            {
                ExecuteScript("rw_unbind", npc);
                ok = GetLocalString(npc, "rw_id") == "";
            }
            if (kind == "mode")
            {
                string mode = RWS(cmd, "mode");
                if ((mode == "auto" || mode == "paused" || mode == "dm") && !(mode == "auto" && GetIsDMPossessed(npc)))
                { RWMode(npc, mode); ok = TRUE; }
            }
            if (kind == "say" && GetLocalString(npc, "rw_mode") == "auto" && !GetIsDMPossessed(npc) && !GetIsDead(npc))
            {
                string speech = RWS(cmd, "text");
                object listener = StringToObject(RWS(cmd, "listener"));
                if(RWS(cmd,"price_stamp")!="" && RWS(cmd,"price_stamp")!=RWShopPriceStamp(npc,listener))
                    {SendMessageToPC(listener,"Shop prices changed while the merchant was answering. Please ask again.");speech="";}
                if (GetIsObjectValid(listener) && RWCanHear(listener, npc, RWHearingRange()) && RWS(cmd,"conversation_revision") == GetLocalString(m,"rw_talk_revision") && GetStringLength(speech) > 0 && GetStringLength(speech) <= 1000)
                {
                    ok = NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK, speech, npc);
                    // Commit a story proposal only after its reviewed speech reached the game.
                    string hook=GetLocalString(m,"rw_story_reply_hook");
                    if(ok && hook!="" && RWS(cmd,"story_action")!="")
                    {
                        SetLocalString(npc,"rw_story_reply",JsonDump(cmd));
                        ExecuteScript(hook,npc);
                        DeleteLocalString(npc,"rw_story_reply");
                    }
                }
            }
        }
        json ack = RWBase("ack", npc);
        ack = JsonObjectSet(ack, "request", JsonString(RWS(cmd, "request")));
        ack = JsonObjectSet(ack, "ok", JsonInt(ok));
        if (RWS(cmd, "kind") == "restore" && !ok)
            ack = JsonObjectSet(ack, "reason", JsonString(GetLocalString(m, "rw_restore_error")));
        RWEmit(ack);
    }
    DelayCommand(1.0, ExecuteScript("rw_tick", m));
}
