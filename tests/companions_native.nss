// Disposable-world fixture only. Never install as a live module hook.
#include "rw_companion"
void Check(int passed,string name)
{WriteTimestampedLogEntry("RW_COMPANION_TEST "+(passed ? "PASS " : "FAIL ")+name);}
void main()
{
    object m=GetModule();SetLocalString(m,"rw_session","companion-native-test");SetLocalInt(m,"rw_tick",10);
    json c=RWBase("companion_config",OBJECT_INVALID);
    c=JsonObjectSet(c,"expires",JsonInt(14));c=JsonObjectSet(c,"enabled",JsonInt(1));
    json bad=JsonObjectSet(c,"session",JsonString("old"));RWCPReply(bad);
    Check(!GetLocalInt(m,"rw_cp_enabled"),"old session cannot enable companions");
    bad=JsonObjectSet(c,"world",JsonString("another-world"));RWCPReply(bad);
    Check(!GetLocalInt(m,"rw_cp_enabled"),"wrong world cannot enable companions");
    bad=JsonObjectSet(c,"expires",JsonInt(9));RWCPReply(bad);
    Check(!GetLocalInt(m,"rw_cp_enabled"),"expired command rejected");
    RWCPReply(c);Check(GetLocalInt(m,"rw_cp_enabled"),"current config accepted");
    object npc=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(10.0,10.0,0.0),0.0));
    Check(GetIsObjectValid(npc),"fixture creature created");
    Check(!RWCPReady(npc,npc),"ordinary NPC cannot impersonate player owner");
    Check(!RWCPOrder(npc,npc,"companion:follow"),"unowned creature cannot follow through adapter");
    Check(!RWCPOrder(npc,npc,"attack"),"unsupported action refused");
    string token=GetLocalString(npc,"rw_cp_token");RWCPInvalidate(npc);
    Check(token!=GetLocalString(npc,"rw_cp_token"),"control change invalidates binding");
    Check(!RWCPChat(npc,"Hello everyone"),"ordinary chat remains untouched");
    Check(GetLocalInt(m,"rw_count")==0,"no persistent world NPC slots allocated");
    Check(RWCPHideChat("/rw companion on"),"administrative command stays private");
    Check(RWCPHideChat("/RW companion Hello"),"slash helper stays private");
    Check(!RWCPHideChat("Whiskers: Hello"),"addressed player Talk remains visible");
    Check(!RWCPHideChat("/rw companionship"),"unrelated command not swallowed");
    Check(!RWCPSpeak(OBJECT_INVALID,"Hello"),"invalid creature cannot speak");
    Check(RWCPSpeak(npc,"*Looks around curiously.*"),"companion emote uses nearby Talk");
    object familiar=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(12.0,10.0,0.0),0.0));
    object other=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(14.0,10.0,0.0),0.0));
    SetName(familiar,"Whiskers Brightpaw");SetName(other,"Mira");
    Check(RWNameMatch(RWAddress("Hello Whiskers"),RWTrimAddress("Hello Whiskers"),familiar),"greeting and short name recognized");
    Check(!RWNameMatch(RWAddress("I mentioned Whiskers yesterday"),RWTrimAddress("I mentioned Whiskers yesterday"),familiar),"mention is not an address");
    Check(RWCPOtherAddress(npc,familiar,"Mira: Hello"),"another NPC takes priority");
    Check(!RWCPOtherAddress(npc,familiar,"Yes, thank you"),"ordinary comma followup remains conversation");
    SetLocalInt(npc,"rw_tr_enabled",TRUE);SetLocalInt(npc,"rw_tr_name_count",1);
    SetLocalObject(npc,"rw_tr_name_0",other);SetLocalString(npc,"rw_tr_name_0","Mira");
    SetLocalString(npc,"rw_tr_name_0_mode","auto");SetLocalString(npc,"rw_tr_name_0_display","Posadera");
    Check(RWCPOtherAddress(npc,familiar,"Posadera, hola"),"translated address switches away from familiar");
    SetName(other,"Whiskers Brightpaw");
    Check(RWCPOtherAddress(npc,familiar,"Whiskers: Hello"),"ambiguous familiar name does not steal conversation");
    SetName(other,"Mira");
    RWCPBeginTalk(npc,familiar);token=GetLocalString(npc,"rw_cp_token");
    RWCPChat(npc,"/rw end");
    Check(!GetLocalInt(npc,"rw_cp_talk_until") && token!=GetLocalString(npc,"rw_cp_token"),"end cancels focus and late replies");
    RWCPBeginTalk(npc,familiar);token=GetLocalString(npc,"rw_cp_token");
    SetLocalString(other,"rw_id","test_other");SetLocalString(other,"rw_mode","auto");
    SetLocalObject(m,"rw_npc_test_other",other);
    Check(RWBeginTalk(npc,other),"world conversation can be selected");
    Check(!GetLocalInt(npc,"rw_cp_talk_until") && token!=GetLocalString(npc,"rw_cp_token"),"click selection cancels familiar focus immediately");
    RWCPBeginTalk(npc,familiar);
    Check(!GetIsObjectValid(GetLocalObject(npc,"rw_talk_target")),"familiar focus clears world selection");
    Check(!RWCPCurrentTalk(npc,familiar) && !GetLocalInt(npc,"rw_cp_talk_until"),"ineligible owner loses focus");
    json observation=RWCPObserve(RWBase("test",OBJECT_INVALID),familiar);
    json rows=JsonObjectGet(observation,"surroundings");int found=FALSE,i;
    for(i=0;i<JsonGetLength(rows);i++)if(RWS(JsonArrayGet(rows,i),"label")=="Mira")found=TRUE;
    Check(RWI(observation,"perception_protocol")==3 && RWI(observation,"perception_tick")==10 && found,"fresh visible creature observation collected");
    SetName(other,"Mira Renamed");
    observation=RWCPObserve(RWBase("test",OBJECT_INVALID),familiar);rows=JsonObjectGet(observation,"surroundings");found=FALSE;
    for(i=0;i<JsonGetLength(rows);i++)if(RWS(JsonArrayGet(rows,i),"label")=="Mira Renamed")found=TRUE;
    Check(found,"next message refreshes observations within same tick");
    WriteTimestampedLogEntry("RW_COMPANION_TEST FINISHED");
}
