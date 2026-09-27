// Disposable native test: persistent authority never claims live-scene actors.
#include "rw_actions"
#include "rw_encounter"
#include "rw_social"
void Check(int ok,string name){WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL"));}
void main()
{
 object area=GetArea(GetObjectByTag("rq_testchest"));
 object n=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(area,Vector(30.34,24.55,0.0),0.0));
 SetEventScript(n,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
 SetLocalObject(GetModule(),"rw_npc_persist_test",n);SetLocalString(n,"rw_id","persist_test");
 SetLocalString(n,"rw_mode","auto");SetLocalInt(n,"rw_epoch",1);
 SetLocalInt(GetModule(),"rw_tick",100);
 json cmd=JsonParse("{\"encounter\":\"meeting\",\"token\":\"activation\",\"persistent_owner\":\"approved\",\"repeat\":false,\"director_hold\":true,\"actors\":[{\"npc\":\"persist_test\",\"epoch\":1}],\"policy\":{\"enabled\":true,\"attack\":false,\"combat_mode\":\"greeting\",\"trigger_radius\":5,\"leave_radius\":10,\"grace_seconds\":5,\"pursuit_radius\":20,\"retreat_hp_percent\":25,\"warning\":\"Please wait.\",\"opening\":\"Hello traveler.\"}}");
 cmd=JsonObjectSet(cmd,"world",JsonString(RWWorld()));
 SetLocalString(n,"rw_live_owner","another-scene");
 Check(!RWEncounterArm(n,cmd),"persistent_cannot_claim_live_actor");
 DeleteLocalString(n,"rw_live_owner");
 Check(RWEncounterArm(n,cmd),"persistent_arm_accepted");
 Check(RWEncounterOwner(n,cmd),"persistent_owner_bound");
 Check(!GetLocalInt(n,"rw_enc_repeat"),"director_controls_completion");
 RWEncounterTick(n);
 Check(GetLocalString(n,"rw_enc_status")=="armed","greeting_waits_without_player");
 SetLocalInt(GetModule(),"rw_tick",110);RWEncounterTick(n);
 Check(GetLocalString(n,"rw_enc_status")=="cancelled","expired_companion_lease_disarms");
 Check(RWEncounterArm(n,cmd) && GetLocalString(n,"rw_enc_status")=="armed","persistent_recovery_rearms_after_lease_loss");
 json wrong=JsonObjectSet(cmd,"persistent_owner",JsonString("wrong"));
 Check(!RWEncounterEnd(n,wrong),"wrong_persistent_owner_rejected");
 Check(!RWSocialOwner(n,wrong),"social_check_wrong_owner_rejected");
 Check(RWSocialOwner(n,cmd),"social_check_persistent_owner_accepted");
 wrong=JsonObjectSet(cmd,"token",JsonString("stale"));
 Check(!RWEncounterEnd(n,wrong),"old_activation_rejected");
 Check(RWEncounterEnd(n,cmd),"persistent_resolution_confirmed");
 Check(GetLocalString(n,"rw_enc_status")=="director_finished","persistent_trigger_finished");
 WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
