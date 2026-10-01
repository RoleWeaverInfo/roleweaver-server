// Disposable-world fixture. Preferences are set on fixture NPCs only to exercise
// policy helpers; production save/menu entry points must refuse these nonplayers.
#include "rw_companion"
void Check(int ok,string label){WriteTimestampedLogEntry("RW_CONTROLS_TEST "+(ok?"PASS ":"FAIL ")+label);}
void FixturePrefs(object owner,json p)
{
 SetLocalInt(owner,"rw_cpp_loaded",TRUE);SetLocalString(owner,"rw_cpp_value",JsonDump(p));
 SetLocalString(owner,"rw_cpp_identity",RWCPSettingsIdentity(owner));SetLocalString(owner,"rw_cpp_session",GetLocalString(GetModule(),"rw_session"));
 SetLocalString(owner,"rw_cpp_generation",GetLocalString(GetModule(),"rw_cpp_generation"));
}
void main()
{
    object m=GetModule();SetLocalString(m,"rw_session","controls-fixture");SetLocalInt(m,"rw_tick",10);
    object owner=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(10.0,10.0,0.0),0.0));
    object other=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(14.0,10.0,0.0),0.0));
    SetLocalString(m,"rw_cpp_generation","test-service");
    json p=RWCPDefaultPrefs();Check(RWCPValidPrefs(p),"default settings accepted");
    Check(!RWCPPreference(owner,"movement") && !RWCPPreference(owner,"inventory"),"unloaded settings block actions until service confirms");FixturePrefs(owner,p);FixturePrefs(other,p);
    Check(RWCPPreference(owner,"movement") && RWCPPreference(owner,"inventory"),"confirmed defaults preserve existing capabilities");
    Check(!RWCPValidPrefs(JsonObjectSet(p,"tone",JsonInt(99))),"out of range style rejected");
    Check(!RWCPValidPrefs(JsonObjectSet(p,"movement",JsonString("1"))),"noninteger permission rejected");
    Check(!RWCPValidPrefs(JsonObjectSet(p,"movement",JsonBool(TRUE))),"boolean wire value rejected");
    Check(!RWCPValidPrefs(JsonObjectSet(p,"version",JsonInt(0))),"unknown preference version rejected");
    Check(!RWCPStorePrefs(owner,p) && !RWCPMenu(owner),"nonplayer cannot save settings or open player controls");
    SetLocalString(owner,"rw_cpp_value","{broken");
    Check(!RWCPPreference(owner,"movement") && !RWCPPreference(owner,"inventory"),"malformed cache fails closed");
    FixturePrefs(owner,p);SetLocalString(owner,"rw_cpp_identity","another-character");
    Check(!RWCPPreferencesReady(owner),"cached preferences cannot cross character or world identities");
    FixturePrefs(owner,p);SetLocalString(owner,"rw_cpp_session","old-game");
    Check(!RWCPPreferencesReady(owner),"new game session rejects old cache");
    FixturePrefs(owner,p);SetLocalString(owner,"rw_cpp_generation","old-service");
    Check(!RWCPPreferencesReady(owner),"service restart or database restore invalidates cached preferences");
    Check(!RWCPAcceptPrefs(JsonObject()),"malformed preference reply cannot impersonate owner");
    json collect=JsonParse("{\"verb\":\"pickup\"}");json delivery=JsonObject();delivery=JsonObjectSet(delivery,"verb",JsonString("give"));delivery=JsonObjectSet(delivery,"target",JsonString(ObjectToString(other)));
    json exchange=JsonParse("{\"verb\":\"exchange\"}");
    FixturePrefs(owner,p);Check(RWCPIWorkAllowed(owner,collect) && RWCPIWorkAllowed(owner,delivery),"default item errands remain available");
    FixturePrefs(owner,JsonObjectSet(p,"collect",JsonInt(0)));
    Check(!RWCPIWorkAllowed(owner,collect) && RWCPIWorkAllowed(owner,delivery),"collection toggle independent of delivery");
    FixturePrefs(owner,JsonObjectSet(p,"deliver",JsonInt(0)));
    Check(!RWCPIWorkAllowed(owner,delivery) && RWCPIWorkAllowed(owner,collect),"delivery toggle independent of collection");
    delivery=JsonObjectSet(delivery,"target",JsonString(ObjectToString(owner)));
    Check(RWCPIWorkAllowed(owner,delivery),"owner may retrieve belongings with other-player delivery disabled");
    FixturePrefs(owner,JsonObjectSet(p,"movement",JsonInt(0)));
    Check(!RWCPIWorkAllowed(owner,collect) && !RWCPIWorkAllowed(owner,delivery) && RWCPIWorkAllowed(owner,exchange),"movement restriction blocks errands but permits exchange in place");
    Check(RWCPPreference(other,"movement"),"settings isolated between owners");
    FixturePrefs(owner,JsonObjectSet(p,"inventory",JsonInt(0)));
    Check(!RWCPIWorkAllowed(owner,collect) && !RWCPIWorkAllowed(owner,exchange),"inventory off blocks all active item actions");
    Check(!RWCPIWorkAllowed(other,JsonParse("{\"verb\":\"attack\"}")),"unknown item action denied");
    SetLocalInt(owner,"rw_cp_talk_until",20);string before=GetLocalString(owner,"rw_cp_token");RWCPEndTalk(owner);RWCPInvalidate(owner);
    Check(!GetLocalInt(owner,"rw_cp_talk_until") && before!=GetLocalString(owner,"rw_cp_token"),"settings-change invalidation ends focus and pending requests");
    WriteTimestampedLogEntry("RW_CONTROLS_TEST FINISHED");
}
