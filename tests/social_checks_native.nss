// Disposable module only: validates policy/ownership and rejects non-player rolls.
#include "rw_social"
void Check(int ok,string name){WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL"));}
void main()
{
 object area=GetArea(GetObjectByTag("rq_testchest"));
 object n=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(area,Vector(30.34,24.55,0.0),0.0));
 SetEventScript(n,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
 SetLocalString(n,"rw_mode","auto");SetLocalString(n,"rw_live_owner","owner");
 SetLocalString(n,"rw_live_scene","scene");SetLocalInt(GetModule(),"rw_tick",100);
 json c=JsonParse("{\"live_owner\":\"owner\",\"encounter\":\"scene\",\"token\":\"activation\",\"settings\":{\"enabled\":true,\"skills\":{\"intimidate\":{\"enabled\":true,\"dc\":15},\"persuade\":{\"enabled\":true,\"dc\":15},\"bluff\":{\"enabled\":true,\"dc\":15}}}}");
 c=JsonObjectSet(c,"world",JsonString(RWWorld()));
 Check(RWSocialSkill("intimidate")==SKILL_INTIMIDATE && RWSocialSkill("persuade")==SKILL_PERSUADE && RWSocialSkill("bluff")==SKILL_BLUFF && RWSocialSkill("attack")==-1,"skill_allowlist");
 Check(!RWSocialSetup(n,JsonObjectSet(c,"live_owner",JsonString("wrong"))),"wrong_owner_rejected");
 Check(RWSocialSetup(n,c),"authorized_policy_accepted");
 Check(GetLocalInt(n,"rw_social_lease")==105,"short_policy_lease");
 SetLocalString(n,"rw_social_cache","[1]");
 Check(RWSocialSetup(n,c) && GetLocalString(n,"rw_social_cache")=="[1]","policy_refresh_preserves_roll_cache");
 c=JsonObjectSet(c,"token",JsonString("next"));
 Check(RWSocialSetup(n,c) && GetLocalString(n,"rw_social_cache")=="[]","new_activation_resets_cache");
 json bad=JsonObjectGet(c,"settings"), skills=JsonObjectGet(bad,"skills"), row=JsonObjectGet(skills,"bluff");
 row=JsonObjectSet(row,"dc",JsonInt(0));skills=JsonObjectSet(skills,"bluff",row);
 bad=JsonObjectSet(bad,"skills",skills);
 Check(!RWSocialSetup(n,JsonObjectSet(c,"settings",bad)),"invalid_dc_rejected");
 c=JsonObjectSet(c,"listener",JsonString(ObjectToString(n)));
 c=JsonObjectSet(c,"skill",JsonString("intimidate"));c=JsonObjectSet(c,"attempt",JsonString("123456789012345678901234"));
 c=JsonObjectSet(c,"combat_event",JsonString("chat:1"));
 SetLocalObject(n,"rw_enc_chat_pc",n);SetLocalString(n,"rw_enc_chat_event","chat:1");
 Check(!RWSocialRoll(n,c) && GetLocalString(n,"rw_social_cache")=="[]","nonplayer_never_rolls");
 SetLocalString(n,"rw_mode","paused");
 Check(!RWSocialSetup(n,c) && !RWSocialRoll(n,c),"paused_actor_rejects_checks");
 WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
