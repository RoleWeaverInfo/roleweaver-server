// Disposable native test world only.
#include "rw_inventory"
void Check(int ok,string name){WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL"));}
json Cmd(object n,string kind,object i)
{json c=JsonObject();c=JsonObjectSet(c,"action",JsonString(kind));c=JsonObjectSet(c,"recipient",JsonString("self"));c=JsonObjectSet(c,"item",JsonString(RWInvRef(i)));SetLocalObject(n,"rw_inv_"+RWInvRef(i),i);c=JsonObjectSet(c,"slot",JsonInt(4));c=JsonObjectSet(c,"power",JsonInt(0));return JsonObjectSet(c,"inventory_revision",JsonString(GetLocalString(n,"rw_inventory_revision")));}
void EndUse(object n,object i,int hp)
{string status=RWInvTaskTick(n);Check(GetCurrentHitPoints(n)>hp,"native_potion_healed");Check(!GetIsObjectValid(i),"potion_consumed");Check(FindSubString(status,"consumed")>=0,"use_result_observed");WriteTimestampedLogEntry("RW_INV_TEST FINISHED");}
void AfterRemove(object n,object i)
{
 Check(RWInvTaskTick(n)=="completed" && RWInvSlot(i,n)<0,"unequip_observed");
 object potion=CreateItemOnObject("nw_it_mpotion001",n);SetIdentified(potion,TRUE);SetDroppableFlag(potion,TRUE);
 ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDamage(3,DAMAGE_TYPE_MAGICAL),n);int hp=GetCurrentHitPoints(n);
 Check(RWInvStart(n,Cmd(n,"use",potion)),"use_accepted");SetLocalString(n,"rw_action_kind","use");RWInvTaskTick(n);DelayCommand(6.0,EndUse(n,potion,hp));
}
void AfterEquip(object n,object i)
{
 Check(RWInvTaskTick(n)=="completed" && GetItemInSlot(4,n)==i,"equip_observed");
 Check(!RWInvSafe(i,n,100),"equipped_transfer_rejected");
 json rows=RWInvRows(n,n);Check(JsonGetLength(rows)>0 && RWI(JsonArrayGet(rows,0),"equipped"),"equipped_visible");
 Check(RWInvStart(n,Cmd(n,"unequip",i)),"unequip_accepted");SetLocalString(n,"rw_action_kind","unequip");RWInvTaskTick(n);DelayCommand(3.0,AfterRemove(n,i));
}
void Begin()
{
 object box=GetObjectByTag("rq_testchest");object n=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",GetLocation(box));SetLocalString(n,"rw_mode","auto");SetAILevel(n,AI_LEVEL_VERY_HIGH);SetEventScript(n,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
 SetLocalInt(n,"rw_inventory_enabled",1);SetLocalString(n,"rw_inventory_revision","123456789012345678901234");
 json p=JsonObject();p=JsonObjectSet(p,"max_value",JsonInt(100));p=JsonObjectSet(p,"equip",JsonInt(1));p=JsonObjectSet(p,"use_items",JsonInt(1));p=JsonObjectSet(p,"usable_resrefs",JsonArrayInsert(JsonArray(),JsonString("nw_it_mpotion001")));SetLocalString(n,"rw_inventory_policy",JsonDump(p));
 object i=CreateItemOnObject("nw_wswdg001",n);SetIdentified(i,TRUE);SetDroppableFlag(i,TRUE);
 Check(!RWInvStart(n,Cmd(n,"use",i)),"unapproved_use_rejected");
 Check(RWInvStart(n,Cmd(n,"equip",i)),"equip_accepted");SetLocalString(n,"rw_action_kind","equip");RWInvTaskTick(n);DelayCommand(3.0,AfterEquip(n,i));
}
void main(){DelayCommand(2.0,Begin());}
