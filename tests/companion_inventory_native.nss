// Disposable test world ONLY. Creates inventory fixtures and a campaign save.
#include "rw_cp_items"
#include "nwnx_events"
void Check(int ok,string label){WriteTimestampedLogEntry("RW_CARGO_TEST "+(ok?"PASS ":"FAIL ")+label);}
void MarkPack(object owner,object pack)
{
 SetLocalInt(pack,"rw_cp_satchel",1);SetLocalInt(pack,"rw_cp_type",GetFamiliarCreatureType(owner));
 SetLocalString(pack,"rw_cp_world",RWWorld());SetLocalString(pack,"rw_cp_owner",RWCPOwnerKey(owner));
}
void Restored(object owner)
{
 object pack=RetrieveCampaignObject("rw_cp_fixture","satchel",GetLocation(owner),owner);
 Check(GetIsObjectValid(pack) && RWCPIPackOwned(owner,pack),"saved satchel retains owner and type binding");
 object item=GetFirstItemInInventory(pack);
 Check(GetIsObjectValid(item) && GetName(item)=="Saved test dagger","saved satchel retains actual item contents");
 Check(RWCPIPack(owner)==pack,"restored satchel reused without creating a second one");
 Check(RWCPIMove(item,pack,owner,10000) && RWCPIContains(owner,item) && !RWCPIContains(pack,item),"recovered item can be withdrawn without familiar");
 Check(!RWCPIMove(item,pack,owner,10000),"recovery cannot replay the same transfer");
 WriteTimestampedLogEntry("RW_CARGO_TEST FINISHED");
}
void main()
{
 string hook=NWNX_Events_GetCurrentEvent();
 if(hook=="NWNX_ON_INVENTORY_ADD_ITEM_AFTER" || hook=="NWNX_ON_INVENTORY_REMOVE_ITEM_AFTER")
 {
  SetLocalObject(GetModule(),"cargo_event_holder",OBJECT_SELF);
  SetLocalString(GetModule(),"cargo_event_name",hook);return;
 }
 object m=GetModule();SetLocalString(m,"rw_session","cargo-native");SetLocalInt(m,"rw_tick",10);SetLocalInt(m,"rw_cp_enabled",TRUE);
 NWNX_Events_SubscribeEvent("NWNX_ON_INVENTORY_ADD_ITEM_AFTER","invtest");
 NWNX_Events_SubscribeEvent("NWNX_ON_INVENTORY_REMOVE_ITEM_AFTER","invtest");
 json c=JsonParse("{\"inventory\":{\"enabled\":1,\"radius\":20,\"max_value\":10000,\"containers\":[]}}");RWCPIConfig(c);
 Check(RWCPIEnabled(),"valid inventory policy accepted");int revision=GetLocalInt(m,"rw_cpi_revision");RWCPIConfig(c);
 Check(revision==GetLocalInt(m,"rw_cpi_revision"),"unchanged policy does not interrupt errands");
 RWCPIConfig(JsonParse("{\"inventory\":{\"enabled\":1,\"radius\":999,\"max_value\":10000,\"containers\":[]}}"));
 Check(!RWCPIEnabled(),"invalid inventory policy disables operations");RWCPIConfig(c);
 object owner=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(10.0,10.0,0.0),0.0));SetName(owner,"Fixture Owner");
 object peer=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(12.0,10.0,0.0),0.0));SetName(peer,"Fixture Recipient");
 object pack=CreateItemOnObject("nw_it_contain001",owner);MarkPack(owner,pack);
 Check(RWCPIPackOwned(owner,pack),"native inventory bag supports familiar storage");
 Check(RWCPIPack(owner)==pack,"existing bound bag reused");
 Check(!RWCPIPackOwned(peer,pack),"another owner cannot access satchel");
 object otherPack=CreateItemOnObject("nw_it_contain001",owner);
 object item=CreateItemOnObject("nw_wswdg001",owner);SetIdentified(item,TRUE);SetDroppableFlag(item,TRUE);
 Check(RWCPIMove(item,owner,pack,10000),"real item moves to satchel");
 Check(GetLocalObject(m,"cargo_event_holder")==pack && GetLocalString(m,"cargo_event_name")=="NWNX_ON_INVENTORY_ADD_ITEM_AFTER","native deposit hook identifies bag for deferred character save");
 Check(RWCPISafe(item,pack,10000),"bag membership checked despite engine possessor being character");
 Check(!RWCPIIncoming(item,owner,pack,10000),"satchel contents excluded from owner deposits");
 Check(!RWCPIMove(item,owner,pack,10000),"duplicate deposit cannot move an item already in satchel");
 SetLocalObject(owner,"rw_cpt_pack",pack);json outRows=RWCPIOptions(owner,pack,"out",10000);
 Check(JsonGetLength(RWCPIOptions(owner,owner,"in",10000,pack))==0,"owner UI excludes current satchel contents");
 Check(RWCPISelection(owner,"out",0,10000),"satchel selection validates item identity and ownership");
 object incoming=CreateItemOnObject("nw_wswdg001",owner);SetIdentified(incoming,TRUE);SetDroppableFlag(incoming,TRUE);
 RWCPIOptions(owner,owner,"in",10000,pack);Check(RWCPISelection(owner,"in",0,10000),"owner item may be deposited");
 NWNX_Item_MoveTo(incoming,pack);
 Check(!RWCPISelection(owner,"in",0,10000),"stale owner selection rejected after item moved into satchel");
 Check(!RWCPISwapOK(pack,owner,item,incoming,10000,TRUE),"owner swap rejects both items in same satchel");
 NWNX_Item_MoveTo(incoming,otherPack);
 Check(GetLocalObject(m,"cargo_event_holder")==otherPack,"native destination event reports actual bag");
 NWNX_Item_MoveTo(incoming,owner);
 Check(GetLocalObject(m,"cargo_event_holder")==otherPack && GetLocalString(m,"cargo_event_name")=="NWNX_ON_INVENTORY_REMOVE_ITEM_AFTER","native withdrawal hook identifies source bag");
 Check(!RWCPISafe(item,otherPack,10000),"item in different bag cannot be taken");
 Check(!RWCPIMove(item,otherPack,peer,10000),"forged source cannot transfer an item");
 SetPlotFlag(item,TRUE);Check(!RWCPIMove(item,pack,peer,10000),"plot item protected");SetPlotFlag(item,FALSE);
 SetDroppableFlag(item,FALSE);Check(!RWCPIMove(item,pack,peer,10000),"nondroppable item protected");SetDroppableFlag(item,TRUE);
 SetIdentified(item,FALSE);Check(!RWCPIMove(item,pack,peer,10000),"unidentified item protected");SetIdentified(item,TRUE);
 Check(!RWCPIMove(item,pack,peer,0),"item value ceiling enforced");
 Check(!RWCPIMove(pack,owner,otherPack,10000),"nested bags cannot be transferred by familiar");
 object offer=CreateItemOnObject("nw_wswdg001",peer);SetIdentified(offer,TRUE);SetDroppableFlag(offer,TRUE);
 Check(!RWCPISwapOK(pack,peer,item,offer,10000,FALSE),"NPC barter requires recipient opt in");
 SetLocalString(peer,"rw_id","cargo_peer");SetLocalString(peer,"rw_mode","auto");SetLocalInt(peer,"rw_inventory_enabled",TRUE);
 SetLocalString(peer,"rw_inventory_policy","{\"give\":1,\"receive\":1,\"exchange\":1,\"max_value\":10000,\"barter_percent\":100}");
 Check(RWCPISwap(pack,peer,item,offer,10000,FALSE)==1 && RWCPIContains(peer,item) && RWCPIContains(pack,offer),"permitted NPC barter moves real objects both ways");
 Check(!RWCPISwap(pack,peer,item,offer,10000,FALSE),"barter cannot replay old object ownership");
 object sword=CreateItemOnObject("nw_wswls001",pack);SetIdentified(sword,TRUE);SetDroppableFlag(sword,TRUE);
 Check(!RWCPISwapOK(pack,peer,sword,item,10000,FALSE),"unequal NPC barter refused");
 // The engine relocates creatures out of blocked tiles; use its actual position.
 object loose=CreateObject(OBJECT_TYPE_ITEM,"nw_wswdg001",GetLocation(owner));SetIdentified(loose,TRUE);SetDroppableFlag(loose,TRUE);
 Check(RWCPIGround(owner,loose),"nearby eligible ground item can be collected");
 SetLocalInt(loose,"rw_no_companion",TRUE);Check(!RWCPIGround(owner,loose),"DM ground-item exclusion enforced");DeleteLocalInt(loose,"rw_no_companion");
 Check(NWNX_Item_MoveTo(loose,pack) && !RWCPIGround(owner,loose),"already collected ground item is no longer available");
 json invalid=RWCPIAdd(JsonArray(),"pickup","Collect item",loose,loose);
 Check(!RWCPITaskStart(owner,peer,JsonArrayGet(invalid,0)),"nonplayer cannot authorize familiar errands");
 Check(!RWCPIWindow(peer,owner,peer,pack),"nonowner cannot open unrestricted exchange");
 json options=JsonArray();int i;for(i=0;i<110;i++)options=RWCPIAdd(options,"pickup","Bounded fixture",loose,loose);
 Check(JsonGetLength(options)==96,"offered action catalog bounded");
 MarkPack(owner,otherPack);Check(!GetIsObjectValid(RWCPIPack(owner)),"duplicate bound bags stop automatic selection");
 DeleteLocalInt(otherPack,"rw_cp_satchel");
 // Simulate save/load: store the single real satchel, remove it, then retrieve.
 // Production uses the owner's server-vault save, never campaign item copies.
 object saved=CreateItemOnObject("nw_wswdg001",pack);SetName(saved,"Saved test dagger");SetIdentified(saved,TRUE);SetDroppableFlag(saved,TRUE);
 NWNX_Item_MoveTo(offer,owner);NWNX_Item_MoveTo(sword,owner);NWNX_Item_MoveTo(loose,owner);
 Check(StoreCampaignObject("rw_cp_fixture","satchel",pack)==1,"native persistence stores satchel and contents");
 DestroyObject(pack);DelayCommand(1.0,Restored(owner));
}
