// Disposable native world only; no commands are sent to the live companion.
#include "rw_actions"
void Check(int ok,string name){WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL"));}
json Command(object npc,string activity)
{
 vector p=GetPosition(npc);json h=JsonObject();h=JsonObjectSet(h,"world",JsonString(RWWorld()));h=JsonObjectSet(h,"area",JsonString(GetResRef(GetArea(npc))));h=JsonObjectSet(h,"area_tag",JsonString(GetTag(GetArea(npc))));h=JsonObjectSet(h,"x",JsonFloat(p.x));h=JsonObjectSet(h,"y",JsonFloat(p.y));h=JsonObjectSet(h,"z",JsonFloat(p.z));
 json c=JsonObject();c=JsonObjectSet(c,"world",JsonString(RWWorld()));c=JsonObjectSet(c,"action",JsonString("village"));c=JsonObjectSet(c,"target",JsonString(activity));c=JsonObjectSet(c,"village",JsonInt(1));c=JsonObjectSet(c,"village_delay",JsonInt(5));c=JsonObjectSet(c,"village_home",h);c=JsonObjectSet(c,"village_radius",JsonInt(4));return JsonObjectSet(c,"request",JsonString("123456789012345678901234"));
}
void Finish(object n,location start)
{
 WriteTimestampedLogEntry("RW_INV_TEST movement "+FloatToString(GetDistanceBetweenLocations(start,GetLocation(n)))+" action "+IntToString(GetCurrentAction(n))+" ai "+IntToString(GetAILevel(n))+" speed "+FloatToString(NWNX_Creature_GetMovementRateFactor(n)));
 Check(GetDistanceBetweenLocations(start,GetLocation(n))>0.2,"native_wander_moved");
 Check(GetDistanceBetweenLocations(GetLocation(n),GetLocalLocation(n,"rw_village_home"))<=9.0,"home_leash");
 SetLocalString(n,"rw_mode","paused");RWActionTick(n);Check(GetLocalString(n,"rw_action_status")=="interrupted","pause_interrupts");
 WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
void Begin()
{
 object area=GetArea(GetObjectByTag("rq_testchest"));vector base=GetPosition(GetObjectByTag("rq_testchest"));base.x=30.34;base.y=24.55;location l=Location(area,base,0.0);json build=JsonObject();build=JsonObjectSet(build,"appearance",JsonInt(6));build=JsonObjectSet(build,"race",JsonInt(6));build=JsonObjectSet(build,"gender",JsonInt(1));build=JsonObjectSet(build,"npc_class",JsonInt(4));build=JsonObjectSet(build,"level",JsonInt(1));object n=RWCreateCreature(build,l);
 SetLocalString(n,"rw_mode","auto");SetAILevel(n,AI_LEVEL_VERY_HIGH);NWNX_Creature_SetMovementRate(n,NWNX_CREATURE_MOVEMENT_RATE_NORMAL);SetCommandable(TRUE,n);SetEventScript(n,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
 Check(!RWStartAction(n,JsonObjectSet(Command(n,"wander"),"village_radius",JsonInt(99))),"invalid_radius_rejected");
 Check(!RWStartAction(n,JsonObjectSet(Command(n,"wander"),"village",JsonInt(0))),"missing_village_flag_rejected");
 Check(!RWStartAction(n,Command(n,"greet")),"no_player_no_greeting");
 SetLocalString(n,"rw_mode","paused");Check(!RWStartAction(n,Command(n,"wander")),"paused_no_dispatch");SetLocalString(n,"rw_mode","auto");
 Check(RWStartAction(n,Command(n,"wander")),"wander_accepted");
 WriteTimestampedLogEntry("RW_INV_TEST area "+GetResRef(area)+" start "+FloatToString(GetPosition(n).x)+" dest "+FloatToString(GetPositionFromLocation(GetLocalLocation(n,"rw_action_destination")).x));
 Check(GetLocalInt(n,"rw_action_next")==GetLocalInt(GetModule(),"rw_tick")+5,"testing_cooldown_five_seconds");
 Check(GetDistanceBetweenLocations(GetLocalLocation(n,"rw_action_destination"),GetLocalLocation(n,"rw_village_home"))<=8.0,"random_destination_bounded");
 location start=GetLocation(n);DelayCommand(5.0,Finish(n,start));
}
void main(){DelayCommand(2.0,Begin());}

