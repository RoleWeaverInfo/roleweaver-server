#include "rw_inc"
#include "rw_companion"
#include "nwnx_chat"
#include "rw_tr_dialog"
object RWChatTarget(object speaker, string text)
{
    object m = GetModule();
    object target = OBJECT_INVALID;
    string address = RWAddress(text);
    string exact = RWTrimAddress(text);
    int best=0, matches=0, knownOther=FALSE;
    int i, count = GetLocalInt(m, "rw_count");
    for (i = 0; i < count; i++)
    {
        object npc = GetLocalObject(m, "rw_slot_" + IntToString(i));
        if (!GetIsObjectValid(npc) || GetLocalString(npc,"rw_id")=="") continue;
        int score=RWNameMatch(address,exact,npc,RWTrNameAlias(speaker,npc));
        if(score==0) continue;
        knownOther=TRUE;
        if (!RWCanHear(speaker,npc,RWHearingRange())) continue;
        if(score>best) {best=score;matches=1;target=npc;}
        else if(score==best) matches++;
    }
    // Addressing an actual nearby player must not leak into the selected NPC conversation.
    object pc=GetFirstPC();
    while(GetIsObjectValid(pc))
    {
        if(pc!=speaker && GetArea(pc)==GetArea(speaker) && GetDistanceBetween(pc,speaker)<=RWHearingRange())
        {
            int score=RWNameMatch(address,exact,pc);
            if(score>0)
            {
                knownOther=TRUE;
                if(score>best) {best=score;matches=1;target=OBJECT_INVALID;}
                else if(score==best) matches++;
            }
        }
        pc=GetNextPC();
    }
    if(matches>1) {RWEndTalk(speaker);return OBJECT_INVALID;}
    if (GetIsObjectValid(target))
    {
        if (!RWDirectAddress() && RWCurrentTalk(speaker) != target)
        { RWEndTalk(speaker); return OBJECT_INVALID; }
        if (RWBeginTalk(speaker, target)) return target;
        return OBJECT_INVALID;
    }
    // Unknown comma clauses such as "Yes, thank you" are ordinary follow-up speech.
    // A colon address or a recognized other character still explicitly changes the target.
    if (knownOther || (address!="" && FindSubString(text,":")>=0))
    { RWEndTalk(speaker); return OBJECT_INVALID; }
    target = RWCurrentTalk(speaker);
    if (GetIsObjectValid(target))
    {
        if (!RWCanHear(speaker,target,RWFollowupRange(speaker,target))) return OBJECT_INVALID;
        RWBeginTalk(speaker,target);
    }
    return target;
}

void RWHandleChat(object speaker, string text, int channel, int moduleEvent, object chatTarget=OBJECT_INVALID)
{
    object m = GetModule();
    if(!GetLocalInt(m,"rw_public_sending") && !(GetIsPC(speaker) && IsInConversation(speaker)))
        RWCPHearPublic(speaker,text,channel,chatTarget);
    if(channel==NWNX_CHAT_CHANNEL_PLAYER_TALK && GetIsPC(speaker) && !GetIsDM(speaker)
        && !GetIsDMPossessed(speaker) && !GetIsPossessedFamiliar(speaker) && RWCPVPlayerChat(speaker,text))
    {
        if(RWCPHideChat(text)){if(moduleEvent)SetPCChatMessage("");else NWNX_Chat_SkipMessage();}
        return;
    }
    if(channel==NWNX_CHAT_CHANNEL_PLAYER_TALK && GetIsPC(speaker)
        && !GetIsDMPossessed(speaker) && !GetIsPossessedFamiliar(speaker) && RWCPChat(speaker,text))
    {
        if(RWCPHideChat(text)){if(moduleEvent)SetPCChatMessage("");else NWNX_Chat_SkipMessage();}
        return;
    }
    if(GetIsPC(speaker) && !GetIsDMPossessed(speaker) && channel==NWNX_CHAT_CHANNEL_PLAYER_TALK && GetStringLowerCase(text)=="/rw language")
    {if(moduleEvent)SetPCChatMessage("");else NWNX_Chat_SkipMessage();RWTrMenu(speaker);return;}
    if(GetIsPC(speaker) && !GetIsDMPossessed(speaker) && channel==NWNX_CHAT_CHANNEL_PLAYER_TALK && GetStringLowerCase(text)=="/rw dialogue")
    {if(moduleEvent)SetPCChatMessage("");else NWNX_Chat_SkipMessage();RWTrDemoBegin(speaker);return;}
    // Native dialogue selections are not new free-form prompts for an AI NPC.
    if(GetLocalInt(speaker,"rw_tr_dialog_active") && IsInConversation(speaker))return;
    if (GetIsDM(speaker) && GetStringLeft(text, 4) == "!rw ")
    {
        if (moduleEvent) SetPCChatMessage(""); else NWNX_Chat_SkipMessage();
        string args = GetSubString(text, 4, 200);
        int split = FindSubString(args, " ");
        string verb = GetStringLeft(args, split);
        args = GetSubString(args, split + 1, 200);
        split = FindSubString(args, " ");
        string id = args;
        string value = "";
        if (split >= 0) { id = GetStringLeft(args, split); value = GetSubString(args, split + 1, 100); }
        if ((verb == "pause" || verb == "resume" || verb == "dm") && GetIsObjectValid(RWFind(id)))
        {
            object npc = RWFind(id);
            if (verb == "resume" && GetIsDMPossessed(npc)) { SendMessageToPC(speaker, "Unpossess the NPC before resuming AI."); return; }
            string mode = "paused";
            if (verb == "resume") mode = "auto";
            if (verb == "dm") mode = "dm";
            RWMode(npc, mode);
            SendMessageToPC(speaker, "Role Weaver: " + id + " is " + mode + ".");
            return;
        }
        if (verb == "name")
        {
            object named=GetNearestObjectByTag(id,speaker);
            if(!GetIsObjectValid(named) || GetIsPC(named) || GetIsDMPossessed(named)
              || GetArea(named)!=GetArea(speaker) || GetDistanceBetween(named,speaker)>10.0)
            {SendMessageToPC(speaker,"Stand within 10 metres of a non-player object with that tag.");return;}
            if(value!="auto" && value!="preserve" && value!="translate")
            {SendMessageToPC(speaker,"Use !rw name TAG auto, preserve or translate.");return;}
            SetLocalInt(named,"rw_tr_name_mode",value=="preserve"?1:(value=="translate"?2:0));
            object viewer=GetFirstPC();while(GetIsObjectValid(viewer))
            {RWTrApplyName(viewer,named,"");SetLocalInt(viewer,"rw_tr_names_seq",GetLocalInt(viewer,"rw_tr_names_seq")+1);viewer=GetNextPC();}
            SendMessageToPC(speaker,"Name translation policy: "+value+". Save rw_tr_name_mode in Aurora to keep it after resets.");return;
        }
        if (verb == "translate")
        {
            object marked = GetNearestObjectByTag(id, speaker);
            int type = GetObjectType(marked);
            if (!GetIsObjectValid(marked) || GetArea(marked) != GetArea(speaker) || GetDistanceBetween(marked, speaker) > 10.0
                || (type != OBJECT_TYPE_ITEM && type != OBJECT_TYPE_DOOR && type != OBJECT_TYPE_PLACEABLE))
            { SendMessageToPC(speaker, "Stand within 10 metres of a placeable, door or item with that tag."); return; }
            if (value != "on" && value != "off")
            { SendMessageToPC(speaker, "Use !rw translate TAG on or !rw translate TAG off."); return; }
            RWTrSetExcluded(marked,value=="off");
            SendMessageToPC(speaker,"World text translation " + value + " for " + GetName(marked) + ". This runtime flag lasts until the object/server resets.");
            return;
        }
        if (verb == "bind")
        {
            object candidate = GetNearestObjectByTag(value, speaker);
            if (GetArea(candidate) != GetArea(speaker) || GetDistanceBetween(candidate, speaker) > 10.0)
            { SendMessageToPC(speaker, "Stand within 10 metres of the creature with that tag."); return; }
            RWBind(candidate, id, speaker); return;
        }
        if (verb == "spawn" && RWValidID(id) && !GetIsObjectValid(RWFind(id)) && RWHasSlot())
        {
            if (!RW_OWNS_PLACEMENTS) { SendMessageToPC(speaker, "This world manages NPC spawning. Bind an existing creature instead."); return; }
            object spawned = CreateObject(OBJECT_TYPE_CREATURE, value, GetLocation(speaker));
            SetLocalString(spawned, "rw_source", "spawn");
            RWBind(spawned, id, speaker); return;
        }
        SendMessageToPC(speaker, "Role Weaver: !rw bind ID TAG | !rw spawn ID RESREF | !rw pause ID | !rw resume ID | !rw dm ID | !rw translate TAG on/off | !rw name TAG auto/preserve/translate");
        return;
    }
    // Only public nearby player talk. Never collect tells, party, DM chat or OOC.
    if (channel != NWNX_CHAT_CHANNEL_PLAYER_TALK || !GetIsPC(speaker) || GetIsDM(speaker) || GetIsDMPossessed(speaker)) return;
    string end = RWTrimAddress(text);
    if (end == "/rw end")
    {
        RWEndTalk(speaker);
        if (moduleEvent) SetPCChatMessage(""); else NWNX_Chat_SkipMessage();
        SendMessageToPC(speaker, "Role Weaver: conversation ended.");
        return;
    }
    if (end == "goodbye" || end == "bye" || end == "farewell") { RWEndTalk(speaker); return; }
    if (GetStringLeft(text, 2) == "//" || GetStringLeft(text, 2) == "((" || GetStringLength(text) > 2000) return;
    object npc = RWChatTarget(speaker, text);
    if (!GetIsObjectValid(npc) || GetIsDMPossessed(npc) || GetLocalString(npc, "rw_mode") != "auto") return;
    json payload = RWBase("chat", npc);
    payload = JsonObjectSet(payload, "conversation_revision", JsonString(GetLocalString(m,"rw_talk_revision")));
    int sequence = GetLocalInt(m, "rw_sequence") + 1;
    SetLocalInt(m, "rw_sequence", sequence);
    payload = JsonObjectSet(payload, "event_id", JsonString(GetLocalString(m, "rw_session") + ":" + IntToString(sequence)));
    SetLocalString(npc,"rw_enc_chat_event",RWS(payload,"event_id"));
    SetLocalObject(npc,"rw_enc_chat_pc",speaker);
    SetLocalInt(npc,"rw_enc_chat_seq",sequence);
    int combatReady=GetLocalString(npc,"rw_enc_status")=="negotiating"
        && GetLocalObject(npc,"rw_enc_target")==speaker
        && GetLocalInt(m,"rw_tick")>=GetLocalInt(npc,"rw_enc_deadline")
        && GetLocalInt(m,"rw_tick")<=GetLocalInt(npc,"rw_enc_warning_expiry")
        && sequence>GetLocalInt(npc,"rw_enc_warning_seq");
    payload=JsonObjectSet(payload,"combat_attack_ready",JsonInt(combatReady));
    payload = JsonObjectSet(payload, "player", JsonString(GetPCPublicCDKey(speaker) + ":" + GetName(speaker)));
    payload = JsonObjectSet(payload, "listener", JsonString(ObjectToString(speaker)));
    payload = JsonObjectSet(payload, "text", JsonString(text));
    payload = JsonObjectSet(payload, "speech_format", JsonInt(1));
    if(GetLocalInt(npc,"rw_merchant_enabled")){RWEmit(RWShopSnapshot(npc));payload=JsonObjectSet(payload,"merchant_quote",RWShopQuote(npc,speaker));}
    // Optional module-owned story context. Player text never selects a script.
    string storyHook = GetLocalString(m,"rw_story_context_hook");
    if (storyHook != "")
    {
        SetLocalObject(m,"rw_story_pc",speaker);
        SetLocalObject(m,"rw_story_npc",npc);
        SetLocalString(m,"rw_story_event",RWS(payload,"event_id"));
        DeleteLocalString(m,"rw_story_context");
        ExecuteScript(storyHook,m);
        string context = GetLocalString(m,"rw_story_context");
        if(context!="") payload=JsonObjectSet(payload,"story",JsonParse(context));
        DeleteLocalString(m,"rw_story_context");
        DeleteLocalObject(m,"rw_story_pc");DeleteLocalObject(m,"rw_story_npc");
        DeleteLocalString(m,"rw_story_event");
    }
    RWEmit(payload);
}
