// Familiar lifecycle and transport. Does not bind rw_slot_, install creature
// scripts, change factions, or persist a creature placement.
#include "rw_inc"
#include "nwnx_chat"
#include "rw_address"
#include "rw_translate"

#include "rw_cp_base"
#include "rw_hearing"
#include "rw_cp_menu"

// Focus is private to the owner. A fresh address opens a short conversation;
// movement, control changes and explicit selection of someone else close it.
int RWCPCurrentTalk(object owner,object familiar)
{
    if(!GetLocalInt(owner,"rw_cp_talk_until"))return FALSE;
    if(!RWCPReady(owner,familiar) || GetLocalObject(owner,"rw_cp_talk_target")!=familiar
        || GetLocalObject(owner,"rw_cp_talk_area")!=GetArea(owner)
        || GetLocalInt(owner,"rw_cp_talk_until")<=GetLocalInt(GetModule(),"rw_tick")
        || GetLocalString(owner,"rw_cp_talk_session")!=GetLocalString(GetModule(),"rw_session")
        || GetLocalString(owner,"rw_cp_talk_policy")!=GetLocalString(GetModule(),"rw_talk_revision")
        || GetDistanceBetween(owner,familiar)>RWHearingRange() || !LineOfSightObject(owner,familiar))
    {RWCPEndTalk(owner);return FALSE;}
    return TRUE;
}
void RWCPBeginTalk(object owner,object familiar)
{
    RWEndTalk(owner);
    SetLocalObject(owner,"rw_cp_talk_target",familiar);
    SetLocalObject(owner,"rw_cp_talk_area",GetArea(owner));
    SetLocalInt(owner,"rw_cp_talk_until",GetLocalInt(GetModule(),"rw_tick")+RWTalkTimeout());
    SetLocalString(owner,"rw_cp_talk_session",GetLocalString(GetModule(),"rw_session"));
    SetLocalString(owner,"rw_cp_talk_policy",GetLocalString(GetModule(),"rw_talk_revision"));
}
// Read-only awareness is sampled only for an owner's actual message. Heartbeats
// carry lifecycle state, not repeated area scans or autonomous model requests.
json RWCPObserve(json e,object familiar,string instruction="")
{
    object owner=GetMaster(familiar);
    // A new turn must not reuse an observation from before crossing an area edge.
    DeleteLocalInt(familiar,"rw_perception_tick");
    e=JsonObjectSet(e,"surroundings",RWSurroundings(familiar));
    e=JsonObjectSet(e,"perception_protocol",JsonInt(3));
    e=JsonObjectSet(e,"perception_tick",JsonInt(GetLocalInt(familiar,"rw_perception_tick")));
    e=JsonObjectSet(e,"perception_truncated",JsonInt(GetLocalInt(familiar,"rw_perception_truncated")));
    e=JsonObjectSet(e,"self_condition",JsonString(RWVisibleCondition(familiar)));
    e=JsonObjectSet(e,"area",JsonString(GetName(GetArea(familiar))));
    e=JsonObjectSet(e,"companion_preferences",RWCPPreferences(owner));
    e=JsonObjectSet(e,"companion_preferences_protocol",JsonInt(2));
    e=JsonObjectSet(e,"hearing_protocol",JsonInt(1));
    e=JsonObjectSet(e,"hearing_enabled",JsonInt(RWCPHearEnabled(owner,familiar)));
    e=JsonObjectSet(e,"heard_speech",RWCPHearRecent(familiar));
    return RWCPVObserve(RWCPIObserve(e,owner,familiar),owner,familiar,instruction);
}
void RWCPTick(object owner)
{
    if(GetLocalInt(owner,"rw_cpp_requested") || GetLocalInt(owner,"rw_cp_on"))RWCPRequestPrefs(owner);
    if(!GetLocalInt(owner,"rw_cp_on") || GetLocalString(owner,"rw_cp_login_session")!=GetLocalString(GetModule(),"rw_session"))return;
    object familiar=RWCPFind(owner);
    if(GetIsObjectValid(familiar))RWCPHearRecent(familiar);
    int ready=RWCPReady(owner,familiar);
    if(familiar!=GetLocalObject(owner,"rw_cp_object")
        || ready!=GetLocalInt(owner,"rw_cp_ready")
        || GetLastAssociateCommand(familiar)!=GetLocalInt(owner,"rw_cp_last_order"))
    {
        RWCPEndTalk(owner);
        RWCPInvalidate(owner);
        SetLocalObject(owner,"rw_cp_object",familiar);
        SetLocalInt(owner,"rw_cp_ready",ready);
        SetLocalInt(owner,"rw_cp_last_order",GetLastAssociateCommand(familiar));
    }
    RWCPCurrentTalk(owner,familiar);
    if(GetIsObjectValid(familiar)){RWCPITaskTick(owner,familiar);RWCPVTick(familiar);}
    if(GetIsObjectValid(familiar))RWEmit(RWCPEvent("companion_state",owner,familiar));
}
int RWCPOrder(object owner,object familiar,string verb)
{
    if(!RWCPReady(owner,familiar) || !RWCPPreference(owner,"movement") || (verb!="companion:follow" && verb!="companion:stay"))return FALSE;
    RWCPVCancel(familiar,"Visit cancelled by a new owner command.",FALSE);
    RWCPICancel(familiar,"Errand cancelled by a new owner command.",FALSE);
    // This adapter uses the stock associate state flags. PW owners may substitute
    // their own adapter script and explicitly return rw_cp_order_ok=TRUE.
    SetLocalString(familiar,"rw_cp_order",verb);
    DeleteLocalInt(familiar,"rw_cp_order_ok");
    string adapter=GetLocalString(GetModule(),"rw_companion_adapter");
    if(adapter=="")adapter="rw_cp_order";
    ExecuteScript(adapter,familiar);
    int ok=GetLocalInt(familiar,"rw_cp_order_ok");
    DeleteLocalString(familiar,"rw_cp_order");DeleteLocalInt(familiar,"rw_cp_order_ok");
    return ok;
}
// Administrative slash commands stay private; in-character addressed Talk remains
// visible to nearby players. Companion speech uses the same channel as world NPCs.
int RWCPHideChat(string text)
{
    string lower=GetStringLowerCase(text);
    return lower=="/rw companion" || GetStringLeft(lower,14)=="/rw companion ";
}
int RWCPSpeak(object familiar,string text)
{
    if(!GetIsObjectValid(familiar) || GetIsDead(familiar) || GetIsDMPossessed(familiar)
        || GetIsPossessedFamiliar(familiar) || text=="" || GetStringLength(text)>1000)return FALSE;
    return RWPublicSpeak(text,familiar);
}
// Matching another character takes priority over follow-up focus, including an
// ambiguous shared name. Ordinary clauses such as "Yes, thank you" do not.
int RWCPOtherAddress(object owner,object familiar,string text)
{
    string address=RWAddress(text), exact=RWTrimAddress(text);
    int i;
    for(i=0;i<GetLocalInt(GetModule(),"rw_count");i++)
    {
        object npc=GetLocalObject(GetModule(),"rw_slot_"+IntToString(i));
        if(GetIsObjectValid(npc) && npc!=familiar && RWNameMatch(address,exact,npc,RWTrNameAlias(owner,npc)))return TRUE;
    }
    object o=GetFirstObjectInArea(GetArea(owner)); int scanned=0;
    while(GetIsObjectValid(o) && scanned<1024)
    {
        if(o!=owner && o!=familiar && GetObjectType(o)==OBJECT_TYPE_CREATURE
            && GetDistanceBetween(owner,o)<=RWHearingRange() && RWNameMatch(address,exact,o,RWTrNameAlias(owner,o)))return TRUE;
        o=GetNextObjectInArea(GetArea(owner));scanned++;
    }
    return FALSE;
}
// Only the owner can address their familiar. Clicking it keeps the stock menu.
int RWCPChat(object owner,string text)
{
    string lower=RWTrimAddress(text);
    int command=RWCPHideChat(text);
    object familiar=RWCPFind(owner);
    string name=GetStringLowerCase(GetName(familiar));int n=GetStringLength(name);
    if(!command && (lower=="/rw end" || lower=="bye" || lower=="goodbye" || lower=="farewell"))
    {RWCPEndTalk(owner);return FALSE;}
    if(!command && (GetStringLeft(lower,1)=="/" || GetStringLeft(lower,2)=="(("
        || IsInConversation(owner)))return FALSE;
    if(!command && !GetLocalInt(owner,"rw_cp_on"))return FALSE;
    string address=RWAddress(text);
    int addressed=n>0 && RWNameMatch(address,lower,familiar,RWTrNameAlias(owner,familiar));
    if(!command && (RWCPOtherAddress(owner,familiar,text)
        || (!addressed && address!="" && FindSubString(text,":")>=0)))
    {RWCPEndTalk(owner);return FALSE;}
    int followup=!command && !addressed;
    if(followup && !RWCPCurrentTalk(owner,familiar))return FALSE;
    if(!GetIsPC(owner) || GetIsDM(owner))return TRUE;
    string body=text;
    if(command)body=GetSubString(text,14,GetStringLength(text));
    if(!command && (GetStringLeft(lower,n+1)==name+":" || GetStringLeft(lower,n+1)==name+","))
        body=GetSubString(text,n+1,GetStringLength(text));
    while(GetStringLeft(body,1)==" ")body=GetSubString(body,1,GetStringLength(body));
    lower=GetStringLowerCase(body);
    if(command && (lower=="settings" || lower=="menu"))
    {RWCPRequestPrefs(owner);if(!RWCPMenu(owner))SendMessageToPC(owner,"Companion settings could not open.");return TRUE;}
    if(command && lower=="cancel")
    {RWCPVCancel(familiar,"Visit cancelled by the owner.",TRUE);RWCPICancel(familiar,"Errand cancelled by the owner.",TRUE);RWCPEndTalk(owner);RWCPInvalidate(owner);SendMessageToPC(owner,"Companion errand cancelled. Collected belongings remain in your satchel.");return TRUE;}
    if(command && lower=="off")
    {RWCPVCancel(familiar,"Companion AI disabled.",TRUE);RWCPICancel(familiar,"Familiar inventory task disabled.",TRUE);SetLocalInt(owner,"rw_cp_on",FALSE);RWCPHearClear(familiar);RWCPEndTalk(owner);RWCPInvalidate(owner);SendMessageToPC(owner,"Role Weaver companion disabled. Your familiar satchel stays in your inventory.");return TRUE;}
    if(command && lower=="recover")
    {
        object pack=RWCPIPack(owner);
        if(!GetIsObjectValid(pack) || !RWCPIWindow(owner,owner,familiar,pack,OBJECT_INVALID,TRUE))SendMessageToPC(owner,"No available familiar satchel. You can also open your existing satchel from your inventory.");
        return TRUE;
    }
    if(command && (lower=="" || lower=="help"))
    {SendMessageToPC(owner,"Use /rw companion settings for your controls. Summon a familiar, then /rw companion on. Address it by name, then continue Talk. Try follow me, stay here, or /rw companion inventory. /rw companion recover retrieves satchel items without a familiar. /rw end finishes chat; /rw companion off disables AI.");return TRUE;}
    if(!GetLocalInt(GetModule(),"rw_cp_enabled"))
    {SendMessageToPC(owner,"Role Weaver companions are disabled by the server owner or the service has not connected.");return TRUE;}
    if(command && lower=="on")
    {
        RWCPRequestPrefs(owner);
        if(!GetIsObjectValid(familiar) || GetMaster(familiar)!=owner)
        {SendMessageToPC(owner,"Summon your familiar first.");return TRUE;}
        SetLocalInt(owner,"rw_cp_on",TRUE);SetLocalString(owner,"rw_cp_login_session",GetLocalString(GetModule(),"rw_session"));RWCPInvalidate(owner);RWCPTick(owner);
        if(RWCPIEnabled() && RWCPPreference(owner,"inventory") && !GetIsObjectValid(RWCPIPack(owner,TRUE)))SendMessageToPC(owner,"The familiar satchel could not be prepared. Check inventory space or ask the DM about duplicate satchels.");
        SendMessageToPC(owner,"Role Weaver familiar enabled. Address it once by name, then continue nearby Talk. Use /rw end to finish. Follow me and stay here work without waiting for AI.");return TRUE;
    }
    if(followup && (!RWCPPreference(owner,"followups") || GetDistanceBetween(owner,familiar)>RWCloseRange()))return FALSE;
    if(!RWCPReady(owner,familiar) || GetDistanceBetween(owner,familiar)>RWHearingRange() || !LineOfSightObject(owner,familiar))
    {SendMessageToPC(owner,"Enable your familiar first and approach it. AI conversation pauses during combat or possession.");return TRUE;}
    if(GetStringLength(body)>1000){SendMessageToPC(owner,"Please use a shorter message.");return TRUE;}
    // Refresh lifecycle before creating a turn so the next heartbeat cannot
    // accidentally invalidate a legitimate request after an area transition.
    RWCPVCancel(familiar,"Visit interrupted by a new owner message.",TRUE);
    RWCPTick(owner);RWCPInvalidate(owner);RWCPBeginTalk(owner,familiar);
    if(lower=="inventory" || lower=="show your inventory" || lower=="open exchange")
    {
        if(!RWCPIExchangeStart(owner,familiar))SendMessageToPC(owner,"Familiar exchange is unavailable. Enable companions and inventory support, and make sure your satchel is present.");
        return TRUE;
    }
    string order="";
    if(lower=="follow" || lower=="follow me")order="companion:follow";
    if(lower=="stay" || lower=="stay here" || lower=="stand your ground")order="companion:stay";
    if(order!="")
    {
        int ok=RWCPOrder(owner,familiar,order);
        if(ok)RWCPSpeak(familiar,order=="companion:follow" ? "*Moves to follow.*" : "*Settles in to wait here.*");
        else SendMessageToPC(owner,"Your familiar cannot accept that command now.");
        return TRUE;
    }
    json e=RWCPObserve(RWCPEvent("companion_chat",owner,familiar),familiar,body);
    e=JsonObjectSet(e,"text",JsonString(body));RWEmit(e);
    return TRUE;
}
void RWCPReply(json cmd)
{
    object m=GetModule();int tick=GetLocalInt(m,"rw_tick");
    if(RWS(cmd,"world")!=RWWorld() || RWS(cmd,"session")!=GetLocalString(m,"rw_session")
        || RWI(cmd,"expires")<tick || RWI(cmd,"expires")>tick+5)return;
    if(RWS(cmd,"kind")=="companion_config")
    {SetLocalInt(m,"rw_cp_enabled",RWI(cmd,"enabled")==1);SetLocalInt(m,"rw_cp_listening",RWI(cmd,"listening_enabled")==1);SetLocalString(m,"rw_cpp_generation",RWS(cmd,"preferences_generation"));RWCPIConfig(cmd);RWCPVConfig(cmd);return;}
    if(RWS(cmd,"kind")=="companion_preferences_reply")
    {
        if(RWCPAcceptPrefs(cmd))
        {
            object player=StringToObject(RWS(cmd,"player"));
            if(GetLocalInt(player,"rw_cp_on") && RWCPIEnabled() && RWCPPreference(player,"inventory"))RWCPIPack(player,TRUE);
            RWCPMenuRefresh(player,"Preferences loaded and saved on the server. Address your familiar when ready.");
        }
        return;
    }
    if(RWS(cmd,"kind")=="companion_visit_reply"){RWCPVReply(cmd);return;}
    object familiar=StringToObject(RWS(cmd,"object"));object owner=GetMaster(familiar);
    int ok=RWCPCurrentTalk(owner,familiar) && RWCPOwnerKey(owner)==RWS(cmd,"owner")
        && GetLocalString(owner,"rw_cp_token")==RWS(cmd,"token")
        && GetLocalInt(owner,"rw_cp_sequence")==RWI(cmd,"sequence")
        && GetLastAssociateCommand(familiar)==GetLocalInt(owner,"rw_cp_last_order")
        && GetDistanceBetween(owner,familiar)<=RWHearingRange() && LineOfSightObject(owner,familiar)
        && GetLocalString(owner,"rw_cp_ack")!=RWS(cmd,"request");
    string verb=RWS(cmd,"action"),text=RWS(cmd,"text");
    int inventory=GetStringLeft(verb,6)=="cpinv:";
    int visit=GetStringLeft(verb,8)=="cpvisit:";
    if(text=="" || GetStringLength(text)>1000 || (verb!="" && verb!="companion:follow" && verb!="companion:stay" && !inventory && !visit))ok=FALSE;
    if(ok && verb!="")
    {if(visit)ok=RWCPVStart(owner,familiar,verb,RWS(cmd,"request"));else ok=inventory?RWCPIStart(owner,familiar,verb):RWCPOrder(owner,familiar,verb);}
    if(ok)
    {
        SetLocalString(owner,"rw_cp_ack",RWS(cmd,"request"));
        // NPC speech is not player input; the chat hook must never send it back
        // into companion generation. Record history only on successful delivery.
        ok=RWCPSpeak(familiar,text);
    }
    json ack=cmd;ack=JsonObjectSet(ack,"kind",JsonString("companion_ack"));
    ack=JsonObjectSet(ack,"ok",JsonInt(ok));RWEmit(ack);
}
