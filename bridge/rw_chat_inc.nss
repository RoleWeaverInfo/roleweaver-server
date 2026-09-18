#include "rw_inc"
#include "nwnx_chat"
// Conservative vocatives: Name:, Name, ... and Hello/Hi/Hey/Greetings[, ] Name.
string RWTrimAddress(string value)
{
    while (GetStringLeft(value, 1) == " ") value = GetSubString(value, 1, GetStringLength(value));
    while (GetStringLength(value) > 0 && FindSubString(" .!?", GetStringRight(value, 1)) >= 0)
        value = GetStringLeft(value, GetStringLength(value) - 1);
    return GetStringLowerCase(value);
}

string RWAddress(string text)
{
    text = RWTrimAddress(text);
    int greeting = FALSE;
    string first = GetStringLeft(text, FindSubString(text, " "));
    if (first == "hello" || first == "hello," || first == "hi" || first == "hi,"
        || first == "hey" || first == "hey," || first == "greetings" || first == "greetings,")
    {
        text = GetSubString(text, GetStringLength(first) + 1, GetStringLength(text));
        greeting = TRUE;
    }
    int split = FindSubString(text, ":");
    int comma = FindSubString(text, ",");
    if (comma >= 0 && (split < 0 || comma < split)) split = comma;
    if (split >= 0) return RWTrimAddress(GetStringLeft(text, split));
    if (greeting) return RWTrimAddress(text);
    return "";
}

// Short names omit one common title, so Captain Beran can be addressed as Beran.
string RWShortName(string name)
{
    name=RWTrimAddress(name);
    int split=FindSubString(name," ");
    if(split<0) return name;
    string first=GetStringLeft(name,split);
    if(FindSubString("|captain|sir|lady|lord|master|mistress|doctor|dr.|archmage|", "|"+first+"|")>=0)
    {
        name=RWTrimAddress(GetSubString(name,split+1,GetStringLength(name)));
        split=FindSubString(name," ");
        if(split<0) return name;
    }
    return GetStringLeft(name,split);
}
int RWNameMatch(string address,string exact,object npc)
{
    string name=RWTrimAddress(GetName(npc));
    string id=GetLocalString(npc,"rw_id");
    if ((address!="" && (address==name || (id!="" && address==id)))
        || exact==name || (id!="" && exact==id)) return 1;
    string shortName=RWShortName(name);
    if(shortName!="" && (address==shortName || exact==shortName)) return 1;
    return 0;
}
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
        int score=RWNameMatch(address,exact,npc);
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

void RWHandleChat(object speaker, string text, int channel, int moduleEvent)
{
    object m = GetModule();
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
        SendMessageToPC(speaker, "Role Weaver: !rw bind ID TAG | !rw spawn ID RESREF | !rw pause ID | !rw resume ID | !rw dm ID");
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
    payload = JsonObjectSet(payload, "player", JsonString(GetPCPublicCDKey(speaker) + ":" + GetName(speaker)));
    payload = JsonObjectSet(payload, "listener", JsonString(ObjectToString(speaker)));
    payload = JsonObjectSet(payload, "text", JsonString(text));
    payload = JsonObjectSet(payload, "speech_format", JsonInt(1));
    if(GetLocalInt(npc,"rw_merchant_enabled")){RWEmit(RWShopSnapshot(npc));payload=JsonObjectSet(payload,"merchant_quote",RWShopQuote(npc,speaker));}
    RWEmit(payload);
}
