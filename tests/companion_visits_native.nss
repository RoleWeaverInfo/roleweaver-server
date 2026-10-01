// Isolated disposable module only. No player impersonation or production hooks.
#include "rw_companion"
void Check(int ok,string label){WriteTimestampedLogEntry("RW_VISIT_TEST "+(ok?"PASS ":"FAIL ")+label);}
void main()
{
    object m=GetModule();SetLocalInt(m,"rw_tick",10);SetLocalInt(m,"rw_cp_enabled",TRUE);
    SetLocalString(m,"rw_session","visit-fixture");SetLocalString(m,"rw_cpp_generation","fixture-generation");
    object familiar=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(30.34,24.55,0.0),0.0));
    vector p=GetPosition(familiar);p.x=p.x+2.0;
    object peer=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetArea(familiar),p,0.0));ChangeFaction(peer,familiar);
    SetEventScript(familiar,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");SetEventScript(peer,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
    SetLocalString(peer,"rw_id","visit_peer");SetLocalString(peer,"rw_mode","auto");SetLocalObject(m,"rw_npc_visit_peer",peer);
    json cfg=JsonParse("{\"visits\":{\"enabled\":1,\"players\":1,\"radius\":20,\"receivers\":[\"visit_peer\"]}}");
    RWCPVConfig(cfg);Check(RWCPVEnabled(),"valid server policy accepted");
    Check(RWCPVReceiver(peer) && RWCPVTarget(familiar,peer),"idle approved visible NPC can receive a visit");
    SetLocalString(peer,"rw_mode","paused");Check(!RWCPVTarget(familiar,peer),"paused NPC cannot receive visit");SetLocalString(peer,"rw_mode","auto");
    SetLocalString(peer,"rw_action_status","running");Check(!RWCPVTarget(familiar,peer),"running NPC action not interrupted");DeleteLocalString(peer,"rw_action_status");
    SetLocalString(peer,"rw_live_scene","encounter");Check(!RWCPVTarget(familiar,peer),"live encounter actors excluded");DeleteLocalString(peer,"rw_live_scene");
    SetLocalString(peer,"rw_persistent_scene","encounter");Check(!RWCPVTarget(familiar,peer),"persistent encounter actors excluded");DeleteLocalString(peer,"rw_persistent_scene");
    RWCPVConfig(JsonParse("{\"visits\":{\"enabled\":1,\"players\":1,\"radius\":20,\"receivers\":[]}}"));
    Check(!RWCPVReceiver(peer) && !RWCPVTarget(familiar,peer),"revoked DM receive permission removes target");
    RWCPVConfig(JsonParse("{\"visits\":{\"enabled\":1,\"players\":1,\"radius\":99,\"receivers\":[]}}"));Check(!RWCPVEnabled(),"invalid radius disables visits");
    RWCPVConfig(cfg);
    Check(!RWCPVStart(peer,familiar,"cpvisit:0","123456789012345678901234"),"nonplayer cannot authorize a visit");
    Check(JsonGetLength(JsonObjectGet(RWCPVObserve(JsonObject(),peer,familiar,"ask a question"),"companion_visits"))==0,"unowned creature receives no visit actions");
    SetLocalString(familiar,"rw_cpv_id","123456789012345678901234");SetLocalObject(familiar,"rw_cpv_target",peer);SetLocalObject(peer,"rw_cpv_visitor",familiar);
    Check(!RWCompanionVisitHeld(peer),"orphaned familiar cannot keep NPC patrol reserved");
    SetLocalString(familiar,"rw_cpv_mode","stay");SetLocalInt(familiar,"rw_cpv_turns",0);
    RWCPVAnswered(familiar);Check(GetLocalString(familiar,"rw_cpv_phase")=="ask" && GetLocalInt(familiar,"rw_cpv_turns")==1,"stay mode permits first followup");
    RWCPVAnswered(familiar);Check(GetLocalString(familiar,"rw_cpv_phase")=="ask" && GetLocalInt(familiar,"rw_cpv_turns")==2,"stay mode permits second followup");
    RWCPVAnswered(familiar);Check(GetLocalString(familiar,"rw_cpv_phase")=="return" && GetLocalInt(familiar,"rw_cpv_turns")==3,"third reply ends bounded visit");
    Check(!GetIsObjectValid(GetLocalObject(peer,"rw_cpv_visitor")),"return releases recipient");
    SetLocalString(familiar,"rw_cpv_mode","return");SetLocalInt(familiar,"rw_cpv_turns",0);RWCPVAnswered(familiar);
    Check(GetLocalString(familiar,"rw_cpv_phase")=="return","ask-and-report returns after one answer");
    int step=GetLocalInt(familiar,"rw_cpv_step");RWCPVReply(JsonParse("{\"action\":\"report\",\"text\":\"forged report\"}"));
    Check(GetLocalInt(familiar,"rw_cpv_step")==step,"forged command cannot advance visit or speak");
    Check(!RWCPVPlayerChat(peer,"/rw companion reply forged"),"nonplayer cannot impersonate a recipient reply");
    RWCPVCancel(familiar,"fixture cancellation",FALSE);
    Check(GetLocalString(familiar,"rw_cpv_id")=="","cancellation clears active visit");
    WriteTimestampedLogEntry("RW_VISIT_TEST FINISHED");
}
