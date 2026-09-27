// Run only in a disposable test world. No player or live companion is needed.
#include "rw_actions"
#include "rw_encounter"
void Check(int ok,string name){WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL"));}
void main()
{
 object area=GetArea(GetObjectByTag("rq_testchest"));location l=Location(area,Vector(30.34,24.55,0.0),0.0);
 object n=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",l);
 SetEventScript(n,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
 SetLocalObject(GetModule(),"rw_npc_combat_test",n);SetLocalString(n,"rw_id","combat_test");
 SetLocalString(n,"rw_mode","auto");SetLocalInt(n,"rw_epoch",1);
 SetLocalLocation(n,"rw_enc_anchor",GetLocation(n));
 SetLocalString(n,"rw_enc_cast","[{\"npc\":\"combat_test\",\"epoch\":1}]");
 SetLocalString(n,"rw_enc_policy","{\"combat_mode\":\"conversation\",\"attack\":true,\"leave_radius\":10,\"grace_seconds\":5}");
 SetLocalString(n,"rw_enc_status","armed");SetLocalInt(n,"rw_enc_lease",1000);
 SetLocalInt(GetModule(),"rw_tick",100);RWEncounterTick(n);
 Check(GetLocalString(n,"rw_enc_status")=="armed","conversation_waits_for_dialogue");
 SetLocalInt(GetModule(),"rw_tick",900);RWEncounterTick(n);
 Check(GetLocalString(n,"rw_enc_status")=="armed","elapsed_time_never_attacks");
 Check(!RWEncounterDecision(n,n,JsonObject()),"nonplayer_and_unsigned_decision_rejected");
 SetLocalString(n,"rw_mode","paused");RWEncounterTick(n);
 Check(GetLocalString(n,"rw_enc_status")=="cancelled","paused_actor_cancels_combat");
 Check(!RWEncounterDecision(n,n,JsonObject()),"paused_decision_rejected");
 Check(!RWEncounterEnd(n,JsonObject()),"unsigned_director_end_rejected");
 SetLocalString(n,"rw_mode","auto");SetLocalString(n,"rw_live_owner","owner");
 SetLocalString(n,"rw_live_scene","scene");
 SetLocalString(n,"rw_enc_token","activation");SetLocalString(n,"rw_enc_id","scene");
 json end=JsonObject();end=JsonObjectSet(end,"world",JsonString(RWWorld()));
 end=JsonObjectSet(end,"token",JsonString("activation"));end=JsonObjectSet(end,"encounter",JsonString("scene"));
 end=JsonObjectSet(end,"live_owner",JsonString("wrong"));
 Check(!RWEncounterEnd(n,end),"wrong_owner_cannot_end_scene");
 end=JsonObjectSet(end,"live_owner",JsonString("owner"));
 Check(RWEncounterEnd(n,end),"authorized_director_ends_scene");
 Check(GetLocalString(n,"rw_enc_status")=="director_finished" && !GetLocalInt(n,"rw_enc_repeat"),"ended_scene_cannot_repeat");
 WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
