// Run in an isolated module with rw_settings set to a disposable Redis prefix.
#include "rw_actions"
#include "rw_encounter"
void Check(int ok,string name){WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL"));}
void main()
{
 object area=GetArea(GetWaypointByTag("rw_arr_cave"));
 object leader=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(area,Vector(24.0,27.0,0.0),270.0));
 object captive=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(area,Vector(22.0,30.0,0.0),270.0));
 object target=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(area,Vector(24.0,24.0,0.0),90.0));
 SetLocalObject(GetModule(),"rw_npc_leader",leader);SetLocalString(leader,"rw_id","leader");
 SetLocalObject(GetModule(),"rw_npc_captive",captive);SetLocalString(captive,"rw_id","captive");
 SetLocalString(leader,"rw_mode","auto");SetLocalInt(leader,"rw_epoch",1);
 SetLocalString(captive,"rw_mode","auto");SetLocalInt(captive,"rw_epoch",1);
 SetLocalInt(GetModule(),"rw_tick",100);
 json cmd=JsonParse("{\"encounter\":\"test\",\"token\":\"activation\",\"persistent_owner\":\"approved\",\"repeat\":false,\"director_hold\":false,\"actors\":[{\"npc\":\"leader\",\"epoch\":1,\"combatant\":true},{\"npc\":\"captive\",\"epoch\":1,\"combatant\":false}],\"policy\":{\"enabled\":true,\"attack\":true,\"combat_mode\":\"conversation\",\"combat_conditions\":\"Native test only\",\"trigger_radius\":5,\"leave_radius\":10,\"grace_seconds\":5,\"pursuit_radius\":15,\"retreat_hp_percent\":25,\"warning\":\"Test warning\"}}");
 cmd=JsonObjectSet(cmd,"world",JsonString(RWWorld()));
 json cast=JsonObjectGet(cmd,"actors");
 json invalid=JsonObjectSet(JsonArrayGet(cast,1),"combatant",JsonString("false"));
 json bad=JsonObjectSet(cmd,"actors",JsonArrayInsert(JsonArrayInsert(JsonArray(),JsonArrayGet(cast,0)),invalid));
 Check(!RWEncounterArm(leader,bad),"malformed_combat_permission_rejected");
 Check(RWEncounterArm(leader,cmd),"mixed_cast_arm_accepted");
 RWEncounterAttack(leader,target,JsonObjectGet(cmd,"policy"),GetLocation(leader));
 Check(GetLocalInt(leader,"rw_combat_active") && GetLocalObject(leader,"rw_combat_target")==target,"combatant_receives_attack");
 Check(!GetLocalInt(captive,"rw_combat_active") && !GetIsObjectValid(GetLocalObject(captive,"rw_combat_target")),"noncombatant_excluded_from_attack");
 WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
