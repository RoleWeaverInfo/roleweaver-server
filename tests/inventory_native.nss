// Isolated native regression fixture. NEVER assign this to a live module.
// Creates test items and creatures only inside the disposable test world.
#include "rw_inventory"
void Check(int ok,string name)
{ WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL")); }
json Command(object npc,string kind,object item=OBJECT_INVALID,string recipient="v2")
{
    json c=JsonObject();c=JsonObjectSet(c,"action",JsonString(kind));c=JsonObjectSet(c,"inventory_revision",JsonString(GetLocalString(npc,"rw_inventory_revision")));
    c=JsonObjectSet(c,"container",JsonString("v1"));c=JsonObjectSet(c,"recipient",JsonString(recipient));
    string ref=RWInvRef(item);SetLocalObject(npc,"rw_inv_"+ref,item);c=JsonObjectSet(c,"item",JsonString(ref));return c;
}
void Task(object npc,string kind)
{SetLocalString(npc,"rw_action_kind",kind);SetLocalInt(npc,"rw_action_deadline",999);}
void CheckBandage(object npc,object peer,object kit,int hp,int selfTest)
{
    string result=RWInvTaskTick(npc);
    Check(result=="completed" && GetCurrentHitPoints(peer)>hp,selfTest?"bandage_self_healing":"bandage_native_healing");
    Check(!GetIsObjectValid(kit) || GetItemStackSize(kit)<1,selfTest?"self_kit_consumed":"kit_consumed_once");
    if(!selfTest)
    {
        object ownKit=CreateItemOnObject("nw_it_medkit001",npc);SetIdentified(ownKit,TRUE);SetDroppableFlag(ownKit,TRUE);
        ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDamage(10,DAMAGE_TYPE_MAGICAL),npc);int before=GetCurrentHitPoints(npc);
        Check(RWInvStart(npc,Command(npc,"aid",ownKit,"self")),"self_aid_accepted");Task(npc,"aid");RWInvTaskTick(npc);
        DelayCommand(8.0,CheckBandage(npc,npc,ownKit,before,TRUE));
    }
    else WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
void Finish(object npc,object peer,object box)
{
    Check(GetIsOpen(box),"container_opened_by_npc");
    Check(RWInvTaskTick(npc)=="completed","inspect_completed");
    SetEventScript(box,EVENT_SCRIPT_PLACEABLE_ON_OPEN,"invtest");Check(!RWInvContainer(npc,box),"scripted_container_rejected");SetEventScript(box,EVENT_SCRIPT_PLACEABLE_ON_OPEN,"");
    object dagger=CreateItemOnObject("nw_wswdg001",box);SetIdentified(dagger,TRUE);SetDroppableFlag(dagger,TRUE);
    Check(RWInvStart(npc,Command(npc,"take",dagger)),"take_accepted");Task(npc,"take");
    Check(RWInvTaskTick(npc)=="completed" && GetItemPossessor(dagger)==npc,"take_ownership");
    Check(RWInvStart(npc,Command(npc,"deposit",dagger)),"deposit_accepted");Task(npc,"deposit");
    Check(RWInvTaskTick(npc)=="completed" && GetItemPossessor(dagger)==box,"deposit_ownership");
    Check(RWInvStart(npc,Command(npc,"fetch",dagger)),"fetch_accepted");Task(npc,"fetch");
    Check(RWInvTaskTick(npc)=="" && GetItemPossessor(dagger)==npc,"fetch_collect");
    Check(RWInvTaskTick(npc)=="completed" && GetItemPossessor(dagger)==peer,"fetch_deliver");
    SetLocalObject(peer,"rw_visible_v2",npc);
    Check(RWInvStart(peer,Command(peer,"give",dagger)),"peer_give_accepted");Task(peer,"give");
    Check(RWInvTaskTick(peer)=="completed" && GetItemPossessor(dagger)==npc,"peer_give_ownership");
    SetPlotFlag(dagger,TRUE);Check(!RWInvSafe(dagger,npc,100),"plot_protected");
    json hidden=RWInvOptions(npc,npc,peer,"rw_test_");Check(JsonGetLength(hidden)==0,"inventory_list_excludes_protected");SetPlotFlag(dagger,FALSE);
    json listed=RWInvOptions(npc,npc,peer,"rw_test_");Check(JsonGetLength(listed)==1 && GetLocalObject(peer,"rw_test_1")==dagger,"inventory_list_maps_real_item");
    Check(FindSubString(JsonGetString(JsonArrayGet(listed,0))," x1 | ")>=0,"inventory_list_quantity_and_value");
    SetLocked(box,TRUE);Check(!RWInvStart(npc,Command(npc,"deposit",dagger)),"locked_container_rejected");SetLocked(box,FALSE);
    object other=CreateItemOnObject("nw_wswdg001",peer);SetIdentified(other,TRUE);SetDroppableFlag(other,TRUE);
    Check(RWInvBarterOK(npc,peer,dagger,other),"npc_barter_permissions");
    Check(RWInvBarterMove(npc,peer,dagger,other)==1 && GetItemPossessor(dagger)==peer && GetItemPossessor(other)==npc,"npc_barter_ownership");
    object sword=CreateItemOnObject("nw_wswls001",npc);SetIdentified(sword,TRUE);SetDroppableFlag(sword,TRUE);
    Check(!RWInvBarterOK(npc,peer,sword,dagger),"unequal_barter_rejected");
    object potion=CreateItemOnObject("nw_it_mpotion001",npc);SetIdentified(potion,TRUE);SetDroppableFlag(potion,TRUE);
    ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDamage(2,DAMAGE_TYPE_MAGICAL),peer);
    int hp=GetCurrentHitPoints(peer);
    Check(RWInvStart(npc,Command(npc,"aid",potion)),"aid_accepted");Task(npc,"aid");
    Check(RWInvTaskTick(npc)=="completed" && GetCurrentHitPoints(peer)>hp,"aid_heals");
    Check(RWInvStart(npc,Command(npc,"deposit",other)),"revision_test_started");Task(npc,"deposit");
    SetLocalString(npc,"rw_inventory_revision","changed");
    Check(RWInvTaskTick(npc)=="permissions changed" && GetItemPossessor(other)==npc,"revocation_stops_transfer");
    SetLocalString(npc,"rw_inventory_revision","123456789012345678901234");
    object kit=CreateItemOnObject("nw_it_medkit001",npc);SetIdentified(kit,TRUE);SetDroppableFlag(kit,TRUE);
    NWNX_Creature_SetSkillRank(npc,SKILL_HEAL,30);
    ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDamage(10,DAMAGE_TYPE_MAGICAL),peer);int before=GetCurrentHitPoints(peer);
    Check(RWInvStart(npc,Command(npc,"aid",kit)),"bandage_aid_accepted");Task(npc,"aid");
    Check(RWInvTaskTick(npc)=="","bandage_queued_once");
    DelayCommand(8.0,CheckBandage(npc,peer,kit,before,FALSE));
}
void Begin()
{
    object box=GetObjectByTag("rq_testchest");Check(GetIsObjectValid(box),"fixture_chest");
    vector p=GetPosition(box);p.x=p.x-1.0;location l=Location(GetArea(box),p,0.0);
    object npc=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",l);object peer=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",l);
    Check(GetIsObjectValid(npc) && GetIsObjectValid(peer),"fixture_npcs");
    SetLocalString(npc,"rw_mode","auto");SetLocalString(peer,"rw_mode","auto");SetLocalString(npc,"rw_id","fixture1");SetLocalString(peer,"rw_id","fixture2");
    SetEventScript(npc,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");SetEventScript(peer,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
    SetAILevel(npc,AI_LEVEL_VERY_HIGH);SetAILevel(peer,AI_LEVEL_VERY_HIGH);ChangeFaction(peer,npc);SetLocalObject(npc,"rw_visible_v1",box);SetLocalObject(npc,"rw_visible_v2",peer);SetLocalInt(box,"rw_visible_serial",1);
    json policy=JsonParse("{\"containers\":[\"rq_testchest\"],\"take\":1,\"deposit\":1,\"give\":1,\"receive\":1,\"exchange\":1,\"fetch\":1,\"heal\":1,\"radius\":40,\"max_value\":100,\"barter_percent\":100}");
    json setup=JsonObjectSet(JsonObjectSet(JsonObjectSet(JsonObject(),"policy",policy),"enabled",JsonInt(1)),"revision",JsonString("123456789012345678901234"));
    Check(RWInvSetup(npc,setup) && RWInvSetup(peer,setup),"setup");
    Check(RWInvStart(npc,Command(npc,"inspect")),"inspect_accepted");Task(npc,"inspect");RWInvTaskTick(npc);
    DelayCommand(5.0,Finish(npc,peer,box));
}
void main(){DelayCommand(2.0,Begin());}
