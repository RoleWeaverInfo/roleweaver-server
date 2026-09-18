"""Run conversation routing in an isolated NWN process, without real players or LLM calls."""

import os
import json
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import time

SCRIPT = r"""#include "rw_chat_inc"
#include "rw_actions"
void Check(int ok, string label) {
    if (!ok) { SetLocalInt(GetModule(), "rw_test_failed", TRUE); WriteTimestampedLogEntry("RW_TEST_FAIL " + label); }
}
void HaggleTests()
{
    Check(RWHaggleDiscount(50)==5 && RWHaggleDiscount(51)==0,"default exact fifty percent boundary");
    Check(RWHaggleDiscount(0)==0 && RWHaggleDiscount(101)==0,"invalid rolls refused");
    Check(RWShopPrice(30,10)==27 && RWShopPrice(100,5)==95,"percentage prices");
    Check(RWShopPrice(4,10)==3 && RWShopPrice(1,10)==1,"whole gold rounding and minimum");
    int i=1;while(i<=500){Check(RWShopPrice(i,0)==i && RWShopPrice(i,10)>=1,"ordinary prices and positive floor");i++;}
    string key=RWKey("haggle:test_customer");string other=RWKey("haggle:other_customer");
    json offer=RWHaggleSave(key,50);Check(RWI(offer,"discount")==5,"offer cached in redis");
    Check(RWI(offer,"seconds_remaining")>590,"offer ten minute expiry");
    offer=RWHaggleSave(key,1);Check(RWI(offer,"discount")==5 && RWI(offer,"roll")==50,"repeat cannot reroll or stack");
    offer=RWHaggleSave(other,51);Check(RWI(offer,"discount")==0,"other customer failure independent");
    offer=RWHaggleSave(other,1);Check(RWI(offer,"discount")==0,"failure also consumes attempt");
    NWNX_Redis_GetResultAsInt(NWNX_Redis_EXPIRE(key,0));
    offer=RWHaggleRead(key);Check(RWI(offer,"version")==0,"expired offer unavailable");
    NWNX_Redis_GetResultAsInt(NWNX_Redis_EXPIRE(other,0));
}
int StockUnits(object shop)
{
    int n=0;object item=GetFirstItemInInventory(shop);while(GetIsObjectValid(item)){n+=GetItemStackSize(item);item=GetNextItemInInventory(shop);}return n;
}
json StockCommand(object npc,string operation,string item,int quantity,string request)
{
    json c=JsonObject();c=JsonObjectSet(c,"world",JsonString(RWWorld()));c=JsonObjectSet(c,"operation",JsonString(operation));
    c=JsonObjectSet(c,"item",JsonString(item));c=JsonObjectSet(c,"quantity",JsonInt(quantity));c=JsonObjectSet(c,"request",JsonString(request));
    c=JsonObjectSet(c,"rules_revision",JsonString(GetLocalString(npc,"rw_merchant_revision")));return JsonObjectSet(c,"stock_revision",JsonString(RWStockRevision(npc)));
}
void FinishInterruptedStock(object npc,int units,object shop)
{
    Check(!GetLocalInt(npc,"rw_stock_editing"),"cancelled edit unlocked");
    Check(GetLocalObject(npc,"rw_shop")==shop && StockUnits(shop)==units,"interrupted edit preserves live stock");
    if (!GetLocalInt(GetModule(),"rw_test_failed")) WriteTimestampedLogEntry("RW_TEST_PASS conversation routing");
    ExecuteScript("rw_init",GetModule());
}
void AfterStockRemove(object npc,int expected)
{
    object shop=GetLocalObject(npc,"rw_shop");Check(StockUnits(shop)==expected,"removed selected row only");
    object restored=RetrieveCampaignObject(RWShopDatabase(),RWShopKey(npc),GetLocation(npc));
    Check(StockUnits(restored)==expected,"edited stock persisted");DestroyObject(restored);
    json cmd=StockCommand(npc,"add","nw_wswdg001",1,"333333333333333333333333");
    Check(RWStockEdit(npc,cmd),"interruption test starts");SetLocalInt(npc,"rw_epoch",GetLocalInt(npc,"rw_epoch")+1);
    DelayCommand(1.0,FinishInterruptedStock(npc,expected,shop));
}
void AfterStockAdd(object npc,object oldShop,string oldRevision)
{
    object shop=GetLocalObject(npc,"rw_shop");Check(shop!=oldShop,"stock edit replaces store");
    Check(StockUnits(shop)==6,"added exact quantity");Check(RWStockRevision(npc)!=oldRevision,"stock revision changed");
    Check(GetLocalString(shop,"rw_offer_revision")=="111111111111111111111111","stock edit invalidates offers");
    json stale=StockCommand(npc,"add","nw_wswdg001",1,"444444444444444444444444");stale=JsonObjectSet(stale,"stock_revision",JsonString(oldRevision));
    Check(!RWStockEdit(npc,stale),"stale stock edit refused");
    object item=GetFirstItemInInventory(shop);int quantity=GetItemStackSize(item);
    json cmd=StockCommand(npc,"remove",ObjectToString(item),quantity,"222222222222222222222222");
    Check(!RWStockEdit(npc,JsonObjectSet(cmd,"quantity",JsonInt(quantity+1))),"wrong removal quantity refused");
    Check(RWStockEdit(npc,cmd),"remove selected row started");DelayCommand(1.0,AfterStockRemove(npc,6-quantity));
}
void FinishShopTests(object npc)
{
    object shop=GetLocalObject(npc,"rw_shop");int count=0;object item=GetFirstItemInInventory(shop);
    while(GetIsObjectValid(item)){count++;item=GetNextItemInInventory(shop);}
    Check(count==4,"finite stock depleted");Check(RWShopSave(npc,shop),"store campaign save");
    DeleteLocalObject(npc,"rw_shop");DestroyObject(shop);
    object restored=RWShopEnsure(npc);count=0;item=GetFirstItemInInventory(restored);
    while(GetIsObjectValid(item)){count++;item=GetNextItemInInventory(restored);}
    Check(count==4,"store restored without restocking sold item");
    string beforeStamp=RWShopPriceStamp(npc,npc);
    SetLocalInt(npc,"rw_stock_revision",GetLocalInt(npc,"rw_stock_revision")+1);
    Check(beforeStamp!=RWShopPriceStamp(npc,npc),"stock changes invalidate spoken quotes");
    json stock=RWShopSnapshot(npc);Check(RWS(stock,"status")=="ready","stock snapshot ready");
    Check(JsonGetLength(JsonObjectGet(stock,"items"))==4,"stock snapshot matches store");
    json rules=JsonParse("{\"enabled\":1,\"chance\":25,\"discount\":7,\"cooldown\":120}");
    Check(RWApplyMerchantRules(npc,rules,"aaaaaaaaaaaaaaaaaaaaaaaa"),"custom haggle rules applied");
    int wins=0;int roll=1;while(roll<=100){if(RWHaggleDiscount(roll,npc)==7)wins++;roll++;}
    Check(wins==25,"exact configured success chance");
    Check(!RWApplyMerchantRules(npc,JsonObjectSet(rules,"discount",JsonInt(11)),"bbbbbbbbbbbbbbbbbbbbbbbb"),"game refuses discount above cap");
    Check(!RWApplyMerchantRules(npc,JsonObjectSet(rules,"chance",JsonInt(101)),"bbbbbbbbbbbbbbbbbbbbbbbb"),"game refuses invalid chance");
    Check(!RWApplyMerchantRules(npc,JsonObjectSet(rules,"cooldown",JsonInt(0)),"bbbbbbbbbbbbbbbbbbbbbbbb"),"game refuses unlimited retries");
    string key=RWKey("haggle:custom_test");json offer=RWHaggleSave(key,25,npc);
    Check(RWI(offer,"discount")==7 && RWI(offer,"seconds_remaining")<=120 && RWI(offer,"chance")==25,"custom cached offer");
    NWNX_Redis_GetResultAsInt(NWNX_Redis_EXPIRE(key,0));
    RWApplyMerchantRules(npc,JsonObjectSet(rules,"chance",JsonInt(0)),"bbbbbbbbbbbbbbbbbbbbbbbb");
    Check(RWHaggleDiscount(1,npc)==0,"zero chance never wins");
    RWApplyMerchantRules(npc,JsonObjectSet(rules,"chance",JsonInt(100)),"bbbbbbbbbbbbbbbbbbbbbbbb");
    Check(RWHaggleDiscount(100,npc)==7,"hundred percent always wins");
    Check(RWApplyMerchantRules(npc,JsonObjectSet(rules,"enabled",JsonInt(0)),"bbbbbbbbbbbbbbbbbbbbbbbb"),"disable haggling applied");
    Check(RWHaggleDiscount(1,npc)==0,"disabled haggling gives no discount");RWApplyMerchantRules(npc,rules,"aaaaaaaaaaaaaaaaaaaaaaaa");
    object catalogue=CreateObject(OBJECT_TYPE_STORE,"rw_shop",GetLocation(npc));
    item=CreateItemOnObject("nw_wswdg001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wswdg001");WriteTimestampedLogEntry("RW_CATALOG nw_wswdg001 "+GetName(item));
    item=CreateItemOnObject("nw_wswss001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wswss001");WriteTimestampedLogEntry("RW_CATALOG nw_wswss001 "+GetName(item));
    item=CreateItemOnObject("nw_wswls001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wswls001");WriteTimestampedLogEntry("RW_CATALOG nw_wswls001 "+GetName(item));
    item=CreateItemOnObject("nw_wdbqs001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wdbqs001");WriteTimestampedLogEntry("RW_CATALOG nw_wdbqs001 "+GetName(item));
    item=CreateItemOnObject("nw_wbwsh001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wbwsh001");WriteTimestampedLogEntry("RW_CATALOG nw_wbwsh001 "+GetName(item));
    item=CreateItemOnObject("nw_waxbt001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_waxbt001");WriteTimestampedLogEntry("RW_CATALOG nw_waxbt001 "+GetName(item));
    item=CreateItemOnObject("nw_waxhn001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_waxhn001");WriteTimestampedLogEntry("RW_CATALOG nw_waxhn001 "+GetName(item));
    item=CreateItemOnObject("nw_wblcl001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wblcl001");WriteTimestampedLogEntry("RW_CATALOG nw_wblcl001 "+GetName(item));
    item=CreateItemOnObject("nw_wblhw001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wblhw001");WriteTimestampedLogEntry("RW_CATALOG nw_wblhw001 "+GetName(item));
    item=CreateItemOnObject("nw_wbwxl001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_wbwxl001");WriteTimestampedLogEntry("RW_CATALOG nw_wbwxl001 "+GetName(item));
    item=CreateItemOnObject("nw_aarcl001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_aarcl001");WriteTimestampedLogEntry("RW_CATALOG nw_aarcl001 "+GetName(item));
    item=CreateItemOnObject("nw_ashsw001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_ashsw001");WriteTimestampedLogEntry("RW_CATALOG nw_ashsw001 "+GetName(item));
    item=CreateItemOnObject("nw_it_mpotion001",catalogue);Check(GetIsObjectValid(item),"catalogue nw_it_mpotion001");WriteTimestampedLogEntry("RW_CATALOG nw_it_mpotion001 "+GetName(item));
    item=CreateItemOnObject("nw_it_mpotion002",catalogue);Check(GetIsObjectValid(item),"catalogue nw_it_mpotion002");WriteTimestampedLogEntry("RW_CATALOG nw_it_mpotion002 "+GetName(item));
    item=CreateItemOnObject("nw_it_mpotion003",catalogue);Check(GetIsObjectValid(item),"catalogue nw_it_mpotion003");WriteTimestampedLogEntry("RW_CATALOG nw_it_mpotion003 "+GetName(item));
    DestroyObject(catalogue);
    json cmd=StockCommand(npc,"add","nw_it_mpotion001",2,"111111111111111111111111");
    Check(!RWStockEdit(npc,JsonObjectSet(cmd,"item",JsonString("unapproved"))),"unapproved stock blueprint refused");
    Check(!RWStockEdit(npc,JsonObjectSet(cmd,"quantity",JsonInt(21))),"quantity bounded in game");
    Check(!RWStockEdit(npc,JsonObjectSet(cmd,"world",JsonString("other"))),"foreign world stock edit refused");
    string revision=RWStockRevision(npc);
    Check(RWStockEdit(npc,cmd),"add stock started");Check(!RWStockEdit(npc,cmd),"concurrent stock edit refused");
    DelayCommand(1.0,AfterStockAdd(npc,restored,revision));
}
void main() {
    HaggleTests();
    object m=GetModule();
    SetLocalString(m,"rw_session","test"); SetLocalInt(m,"rw_tick",100);
    object area=GetObjectByTag("starting_area");
    location loc=Location(area,Vector(20.0,14.0,0.0),0.0);
    object a=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",loc);
    object b=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",loc);
    object mira=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",loc);
    object orren=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",loc);
    SetName(mira,"Mira"); SetName(orren,"Orren");
    SetLocalString(mira,"rw_id","mira"); SetLocalString(orren,"rw_id","orren");
    SetLocalString(mira,"rw_mode","auto"); SetLocalString(orren,"rw_mode","auto");
    SetLocalObject(m,"rw_npc_mira",mira); SetLocalObject(m,"rw_npc_orren",orren);
    SetLocalObject(m,"rw_slot_0",mira); SetLocalObject(m,"rw_slot_1",orren); SetLocalInt(m,"rw_count",2);
    Check(!GetIsObjectValid(RWChatTarget(a,"Hello everyone")),"unaddressed starts nothing");
    Check(!GetIsObjectValid(RWChatTarget(a,"I spoke with Mira yesterday")),"name mention ignored");
    Check(RWChatTarget(a,"Mira: Hello")==mira,"colon address");
    Check(RWChatTarget(a,"What happened next?")==mira,"followup");
    Check(!GetIsObjectValid(RWChatTarget(b,"What happened next?")),"bystander excluded");
    Check(RWChatTarget(a,"Yes, thank you.")==mira,"comma clause keeps target");
    Check(RWChatTarget(a,"I agree, but what next?")==mira,"sentence comma keeps target");
    SetName(mira,"Mira Stone");SetName(orren,"Orren Hill");
    Check(RWChatTarget(b,"Mira, hello")==mira,"first name starts conversation");
    Check(RWChatTarget(b,"Tell me more.")==mira,"first name not required again");
    SetName(orren,"Mira Hill");
    Check(!GetIsObjectValid(RWChatTarget(b,"Mira, hello")),"ambiguous first name refused even when also stable id");
    Check(RWChatTarget(b,"Mira Stone: hello")==mira,"full name resolves first name ambiguity");
    SetName(orren,"Captain Beran");
    Check(RWChatTarget(b,"Beran, hello")==orren,"short name skips title");
    RWEndTalk(b);
    Check(!GetIsObjectValid(RWChatTarget(b,"Captain, hello")),"title alone does not switch or start");
    SetName(mira,"Mira");SetName(orren,"Orren");RWEndTalk(b);

    Check(RWChatTarget(b,"Orren, hello")==orren,"other player own target");
    Check(RWCurrentTalk(a)==mira && RWCurrentTalk(b)==orren,"independent targets");
    Check(RWChatTarget(b,"Hello, Mira")==mira,"greeting joins same npc");
    Check(RWChatTarget(a,"Hello Mira!")==mira,"greeting without comma");
    Check(!GetIsObjectValid(RWChatTarget(a,"Kevin: shall we leave?")),"address someone else");
    Check(!GetIsObjectValid(RWCurrentTalk(a)),"old target cleared");
    Check(RWBeginTalk(a,mira),"selection begins");
    SetLocalInt(m,"rw_tick",279); Check(RWCurrentTalk(a)==mira,"before expiry");
    SetLocalInt(m,"rw_tick",280); Check(!GetIsObjectValid(RWCurrentTalk(a)),"expiry");
    RWBeginTalk(a,mira); SetLocalString(mira,"rw_mode","paused");
    Check(!GetIsObjectValid(RWChatTarget(a,"Mira: Hello")),"paused no redirect");
    Check(!GetIsObjectValid(RWCurrentTalk(a)),"paused clears"); SetLocalString(mira,"rw_mode","auto");
    RWBeginTalk(a,mira); SetLocalInt(mira,"rw_epoch",2);
    Check(!GetIsObjectValid(RWCurrentTalk(a)),"control change clears");
    RWBeginTalk(a,mira); SetLocalString(m,"rw_session","new");
    Check(!GetIsObjectValid(RWCurrentTalk(a)),"module session clears");
    SetName(orren,"Mira");
    Check(!GetIsObjectValid(RWChatTarget(a,"Mira: Hello")),"ambiguous name ignored");
    Check(RWChatTarget(a,"orren: Hello")==orren,"unique id resolves ambiguity");
    Check(RWBeginTalk(a,mira) && RWCurrentTalk(a)==mira,"selection resolves duplicate name");
    object far=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",Location(area,Vector(27.0,14.0,0.0),0.0));
    Check(RWChatTarget(far,"orren: Hello")==orren,"direct address hearing range");
    Check(!GetIsObjectValid(RWChatTarget(far,"What next?")),"followup requires close range");
    Check(RWCurrentTalk(far)==orren,"target retained while catching up inside hearing");
    object middle=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",Location(area,Vector(25.0,14.0,0.0),0.0));
    Check(!RWCanHear(middle,orren,RWSelectionRange()),"Talk To still requires three metres");
    RWBeginTalk(middle,orren);Check(RWChatTarget(middle,"Tell me more")==orren,"five metre followup allowed");
    SetLocalString(orren,"rw_action_status","running");SetLocalString(orren,"rw_action_kind","walk");
    Check(RWChatTarget(far,"I am following you")==orren,"walking followup uses hearing range");
    SetLocalString(orren,"rw_action_status","completed");
    Check(RWChatTarget(far,"We have arrived")==orren,"arrival grace permits catching up");
    SetLocalInt(m,"rw_tick",GetLocalInt(m,"rw_tick")+11);
    Check(!GetIsObjectValid(RWChatTarget(far,"Still distant")),"arrival grace expires");
    Check(RWCurrentTalk(far)==orren,"selection survives arrival grace");
    DeleteLocalString(orren,"rw_action_status");DeleteLocalString(orren,"rw_action_kind");

    object distant=CreateObject(OBJECT_TYPE_CREATURE,"innkeeper",Location(area,Vector(5.0,14.0,0.0),0.0));
    Check(!GetIsObjectValid(RWChatTarget(distant,"orren: Hello")),"out of hearing range");
    string old=GetEventScript(mira,EVENT_SCRIPT_CREATURE_ON_DIALOGUE);
    RWInstallTalk(mira); RWInstallTalk(mira);
    Check(GetEventScript(mira,EVENT_SCRIPT_CREATURE_ON_DIALOGUE)=="rw_talk","talk hook installed");
    Check(GetLocalString(mira,"rw_old_dialogue")==old,"original preserved once");
    ExecuteScript("rw_unbind",mira);
    Check(GetEventScript(mira,EVENT_SCRIPT_CREATURE_ON_DIALOGUE)==old,"unbind restores hook");
    Check(!GetIsObjectValid(RWCurrentTalk(a)),"unbind invalidates conversation");
    SetName(orren,"Orren");
    Check(RWSelectionRange()==3.0 && RWCloseRange()==6.0 && RWHearingRange()==10.0 && RWTalkTimeout()==180 && RWFollowHearing(),"default controls");
    json rules=RWConversationPolicy();
    Check(!RWApplyConversationPolicy(JsonObject(),"aaaaaaaaaaaaaaaaaaaaaaaa"),"reject missing fields");
    rules=JsonObjectSet(rules,"hearing_range",JsonInt(21));
    Check(!RWApplyConversationPolicy(rules,"aaaaaaaaaaaaaaaaaaaaaaaa"),"reject excessive hearing range");
    rules=JsonObjectSet(rules,"hearing_range",JsonInt(8));
    rules=JsonObjectSet(rules,"close_range",JsonInt(8));
    rules=JsonObjectSet(rules,"timeout",JsonInt(15));
    rules=JsonObjectSet(rules,"direct_address",JsonInt(0));
    rules=JsonObjectSet(rules,"line_of_sight",JsonInt(0));
    RWBeginTalk(b,orren);
    Check(RWApplyConversationPolicy(rules,"aaaaaaaaaaaaaaaaaaaaaaaa"),"apply valid rules");
    Check(!GetIsObjectValid(RWCurrentTalk(b)),"rule change ends prior targets");
    Check(RWCloseRange()==8.0 && RWHearingRange()==8.0 && RWTalkTimeout()==15 && !RWRequireSight(),"custom controls applied");
    Check(!GetIsObjectValid(RWChatTarget(b,"Orren: Hello")),"selection-only blocks voice start");
    RWBeginTalk(b,orren);
    Check(RWChatTarget(b,"Orren: Hello")==orren,"selected NPC still accepts address");
    Check(RWApplyConversationPolicy(rules,"aaaaaaaaaaaaaaaaaaaaaaaa") && RWCurrentTalk(b)==orren,"retry does not clear target");
    RWBeginTalk(far,orren);
    Check(RWChatTarget(far,"What next?")==orren,"custom close range used");
    SetLocalInt(m,"rw_tick",GetLocalInt(m,"rw_tick")+15);
    Check(!GetIsObjectValid(RWCurrentTalk(far)),"custom timeout used");
    RWBeginTalk(b,orren);
    Check(RWApplyConversationPolicy(rules,"bbbbbbbbbbbbbbbbbbbbbbbb") && !GetIsObjectValid(RWCurrentTalk(b)),"explicit reset clears target");
    rules=JsonObjectSet(rules,"close_range",JsonInt(3));
    rules=JsonObjectSet(rules,"hearing_range",JsonInt(4));
    rules=JsonObjectSet(rules,"direct_address",JsonInt(1));
    RWApplyConversationPolicy(rules,"cccccccccccccccccccccccc");
    Check(!GetIsObjectValid(RWChatTarget(far,"Orren: Hello")),"custom hearing range enforced");
    json actionCmd=JsonObject();
    actionCmd=JsonObjectSet(actionCmd,"world",JsonString(RWWorld()));
    actionCmd=JsonObjectSet(actionCmd,"request",JsonString("eeeeeeeeeeeeeeeeeeeeeeee"));
    actionCmd=JsonObjectSet(actionCmd,"action",JsonString("gesture"));
    actionCmd=JsonObjectSet(actionCmd,"target",JsonString("attack"));
    Check(!RWStartAction(orren,actionCmd),"reject unapproved animation");
    actionCmd=JsonObjectSet(actionCmd,"target",JsonString("bow"));
    SetLocalString(orren,"rw_mode","paused");Check(!RWStartAction(orren,actionCmd),"paused actions refused");
    SetLocalString(orren,"rw_mode","auto");
    Check(RWStartAction(orren,actionCmd),"approved gesture accepted");
    Check(!RWStartAction(orren,actionCmd),"duplicate actionCmd refused");
    RWMode(orren,"paused");Check(GetLocalString(orren,"rw_action_status")=="interrupted","pause stops actionCmd");
    SetLocalString(orren,"rw_mode","auto");SetLocalInt(m,"rw_tick",GetLocalInt(m,"rw_tick")+20);
    actionCmd=JsonObjectSet(actionCmd,"request",JsonString("ffffffffffffffffffffffff"));
    Check(RWStartAction(orren,actionCmd),"gesture after cooldown");
    SetLocalInt(m,"rw_tick",GetLocalInt(m,"rw_tick")+3);RWActionTick(orren);
    Check(GetLocalString(orren,"rw_action_status")=="completed","gesture completion");
    SetLocalInt(orren,"rw_action_next",0);
    json destination=JsonObject();
    destination=JsonObjectSet(destination,"id",JsonString("test"));
    destination=JsonObjectSet(destination,"world",JsonString(RWWorld()));
    destination=JsonObjectSet(destination,"area",JsonString(GetResRef(area)));
    destination=JsonObjectSet(destination,"area_tag",JsonString(GetTag(area)));
    destination=JsonObjectSet(destination,"x",JsonFloat(100.0));destination=JsonObjectSet(destination,"y",JsonFloat(14.0));destination=JsonObjectSet(destination,"z",JsonFloat(0.0));destination=JsonObjectSet(destination,"facing",JsonFloat(0.0));
    actionCmd=JsonObjectSet(actionCmd,"action",JsonString("walk"));actionCmd=JsonObjectSet(actionCmd,"target",JsonString("test"));
    actionCmd=JsonObjectSet(actionCmd,"request",JsonString("abababababababababababab"));
    actionCmd=JsonObjectSet(actionCmd,"destination",destination);
    Check(!RWStartAction(orren,actionCmd),"reject walk beyond 40m");
    destination=JsonObjectSet(destination,"x",JsonFloat(24.0));actionCmd=JsonObjectSet(actionCmd,"destination",destination);
    Check(RWStartAction(orren,actionCmd),"walk accepted");
    SetLocalInt(m,"rw_tick",GetLocalInt(m,"rw_tick")+30);RWActionTick(orren);
    Check(GetLocalString(orren,"rw_action_status")=="timed out","blocked walk times out");
    SetLocalInt(orren,"rw_action_next",0);DeleteLocalString(orren,"rw_action_request");
    SetEventScript(orren,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
    actionCmd=JsonObjectSet(actionCmd,"action",JsonString("home"));
    actionCmd=JsonObjectSet(actionCmd,"request",JsonString("bcbcbcbcbcbcbcbcbcbcbcbc"));
    Check(RWStartAction(orren,actionCmd),"return home uses approved location");RWMode(orren,"paused");SetLocalString(orren,"rw_mode","auto");
    SetLocalString(orren,"rw_action_status","running");SetLocalString(orren,"rw_action_kind","lead");
    SetLocalInt(orren,"rw_action_epoch",GetLocalInt(orren,"rw_epoch"));SetLocalInt(orren,"rw_action_deadline",GetLocalInt(m,"rw_tick")+120);
    SetLocalObject(orren,"rw_action_player",far);RWActionTick(orren);
    Check(GetLocalString(orren,"rw_action_status")=="waiting for player","lead waits for lagging player");
    SetLocalObject(orren,"rw_action_player",a);RWActionTick(orren);
    Check(GetLocalString(orren,"rw_action_status")=="running","lead resumes when player catches up");
    RWMode(orren,"paused");Check(GetLocalString(orren,"rw_action_status")=="interrupted","lead obeys DM pause");
    SetLocalString(orren,"rw_mode","auto");SetLocalInt(orren,"rw_action_next",0);DeleteLocalString(orren,"rw_action_request");
    SetLocalInt(orren,"rw_merchant_enabled",TRUE);object shop=RWShopEnsure(orren);
    Check(GetIsObjectValid(shop),"store created");int itemCount=0;object item=GetFirstItemInInventory(shop);
    while(GetIsObjectValid(item)){itemCount++;Check(GetGoldPieceValue(item)>0,"actual weapon value positive");WriteTimestampedLogEntry("RW_SHOP_ITEM "+GetName(item)+" "+IntToString(GetGoldPieceValue(item)));item=GetNextItemInInventory(shop);}
    Check(itemCount==5,"five finite weapons seeded");Check(!RWShopOpen(orren,a),"non-player cannot open shop");
    DestroyObject(GetFirstItemInInventory(shop));
    DelayCommand(1.0,FinishShopTests(orren));
}"""


def check_transport(prefix):
    from roleweaver.redis_wire import Redis

    redis = Redis(port=6379)

    def hello(predicate=lambda event: True):
        end = time.monotonic() + 7
        while time.monotonic() < end:
            raw = redis.call("LPOP", prefix + ":events")
            if raw:
                event = json.loads(raw)
                if event.get("kind") == "hello" and predicate(event):
                    return event
            else:
                time.sleep(0.1)
        raise AssertionError("Game conversation settings confirmation timed out")

    first = hello()
    assert first["conversation_protocol"] == 2
    revision = "dddddddddddddddddddddddd"
    rules = dict(
        selection_range=2,
        close_range=2,
        hearing_range=4,
        timeout=30,
        line_of_sight=1,
        direct_address=1,
        follow_hearing=1,
    )
    command = dict(
        kind="conversation_settings",
        world="test",
        session=first["session"],
        expires=first["tick"] + 5,
        revision=revision,
        settings=rules,
    )
    for overrides in (dict(world="wrong"), dict(session="stale"), dict(expires=0)):
        redis.call(
            "RPUSH", prefix + ":commands", json.dumps(dict(command, **overrides))
        )
        observed = hello(lambda e: e["tick"] >= first["tick"] + 2)
        assert observed["conversation_revision"] != revision
        first = observed
        command["expires"] = first["tick"] + 5
    redis.call("RPUSH", prefix + ":commands", json.dumps(command))
    applied = hello(lambda e: e["conversation_revision"] == revision)
    assert applied["conversation"] == rules
    print(
        "PASS native settings transport: stale/foreign commands refused; valid rules echoed by game"
    )

    def event_where(predicate, seconds=8):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            raw = redis.call("LPOP", prefix + ":events")
            if raw:
                event = json.loads(raw)
                if predicate(event):
                    return event
            else:
                time.sleep(0.05)
        raise AssertionError("Action transport confirmation timed out")

    state = event_where(lambda e: e.get("kind") == "state" and e.get("npc") == "orren")
    assert applied["actions_protocol"] == 6
    action = dict(
        kind="controlled_action",
        npc="orren",
        world="test",
        session=state["session"],
        epoch=state["epoch"],
        expires=state["tick"] + 5,
        request="ac" * 12,
        action="gesture",
        target="bow",
    )
    redis.call(
        "RPUSH",
        prefix + ":commands",
        json.dumps(dict(action, epoch=state["epoch"] - 1)),
    )
    rejected = event_where(
        lambda e: e.get("kind") == "ack" and e.get("request") == action["request"]
    )
    assert rejected["ok"] == 0
    state = event_where(lambda e: e.get("kind") == "state" and e.get("npc") == "orren")
    action.update(epoch=state["epoch"], expires=state["tick"] + 5)
    redis.call("RPUSH", prefix + ":commands", json.dumps(action))
    accepted = event_where(
        lambda e: e.get("kind") == "ack" and e.get("request") == action["request"]
    )
    assert accepted["ok"] == 1
    state = event_where(
        lambda e: e.get("kind") == "state"
        and e.get("npc") == "orren"
        and e.get("action_status") == "running"
    )
    stop = dict(
        kind="controlled_stop",
        npc="orren",
        session=state["session"],
        epoch=state["epoch"],
        expires=state["tick"] + 5,
        request="ad" * 12,
    )
    redis.call("LPUSH", prefix + ":commands", json.dumps(stop))
    stopped = event_where(
        lambda e: e.get("kind") == "state"
        and e.get("npc") == "orren"
        and e.get("action_status") == "interrupted"
    )
    assert stopped["epoch"] > state["epoch"]
    state = event_where(
        lambda e: e.get("kind") == "state"
        and e.get("npc") == "orren"
        and e["tick"] >= state["tick"] + 21,
        30,
    )
    point = dict(
        id="test",
        world="test",
        area=state["area_resref"],
        area_tag=state["area_tag"],
        x=24.0,
        y=14.0,
        z=0.0,
        facing=0.0,
    )
    action.update(
        request="ae" * 12,
        action="walk",
        target="test",
        destination=point,
        epoch=state["epoch"],
        expires=state["tick"] + 5,
    )
    redis.call("RPUSH", prefix + ":commands", json.dumps(action))
    accepted = event_where(
        lambda e: e.get("kind") == "ack" and e.get("request") == action["request"]
    )
    assert accepted["ok"] == 1
    arrived = event_where(
        lambda e: e.get("kind") == "state"
        and e.get("npc") == "orren"
        and e.get("action_request") == action["request"]
        and e.get("action_status") != "running",
        35,
    )
    assert arrived["action_status"] == "completed", arrived["action_status"]
    assert ((arrived["x"] - 24.0) ** 2 + (arrived["y"] - 14.0) ** 2) ** 0.5 <= 1.5
    print("PASS native actual walking: reached recorded endpoint with normal movement")
    print(
        "PASS native controlled actions: allowlist, pause, cooldown, completion, movement bounds, timeout, stale epoch and stop transport"
    )


def main():
    base = Path(__file__).resolve().parent.parent
    native = Path(
        os.environ.get(
            "RW_NATIVE", "/home/roleweaver/Documents/RoleWeaver-Native-Server"
        )
    )
    sys.path.insert(0, str(base))
    sys.path.insert(0, str(base / "tools"))
    from module_copy import make_copy

    with tempfile.TemporaryDirectory(prefix="rw-conversation-test-") as directory:
        root = Path(directory)
        userdata = root / "userdata"
        override = userdata / "override"
        override.mkdir(parents=True)
        original = make_copy(
            native / "userdata/modules/DMFI MP Starter Mod.mod",
            userdata / "modules/rw_talktest.mod",
            "rw_testload",
        )
        for source in (base / "bridge").glob("*.nss"):
            (override / source.name).write_bytes(source.read_bytes())
        (override / "rw_shop.utm").write_bytes(
            (base / "assets/rw_shop.utm").read_bytes()
        )
        prefix = "roleweaver:test:" + secrets.token_hex(8)
        (override / "rw_settings.nss").write_text(
            'const string RW_WORLD="test";const string RW_REDIS_PREFIX="'
            + prefix
            + '";const int RW_OWNS_PLACEMENTS=0;const int RW_REGISTERS_CHAT=0;'
        )
        (override / "rw_testload.nss").write_text(
            'void main(){ExecuteScript("'
            + original
            + '",OBJECT_SELF);DelayCommand(1.0,ExecuteScript("rw_testtalk",GetModule()));}'
        )
        (override / "rw_testtalk.nss").write_text(SCRIPT)
        for name in (
            "rw_testload",
            "rw_testtalk",
            "rw_talk",
            "rw_unbind",
            "rw_init",
            "rw_tick",
            "rw_possess",
            "rw_chat",
            "rw_shop_evt",
        ):
            result = subprocess.run(
                [
                    str(base / "tools/nwnsc"),
                    "-n",
                    str(native / "runtime"),
                    "-i",
                    str(native / "nwscripts") + ";" + str(override),
                    str(override / (name + ".nss")),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
        env = dict(
            os.environ,
            LD_PRELOAD=str(native / "plugins/NWNX_Core.so"),
            LD_LIBRARY_PATH=str(native / "plugins"),
            NWNX_CORE_LOAD_PATH=str(native / "plugins"),
            NWNX_CORE_SKIP_ALL="1",
            NWNX_PLAYER_SKIP="n",
            NWNX_CORE_LOG_LEVEL="6",
            NWNX_CHAT_SKIP="n",
            NWNX_EVENTS_SKIP="n",
            NWNX_REDIS_SKIP="n",
            NWNX_REDIS_HOST="127.0.0.1",
            NWNX_REDIS_PORT="6379",
            NWNX_CORE_LOG_FILE_PATH=str(root / "nwnx.log"),
        )
        with (root / "console.log").open("w") as log:
            process = subprocess.Popen(
                [
                    str(native / "runtime/bin/linux-x86/nwserver-linux"),
                    "-userdirectory",
                    str(userdata),
                    "-module",
                    "rw_talktest",
                    "-port",
                    "5129",
                    "-publicserver",
                    "0",
                    "-playerpassword",
                    secrets.token_hex(16),
                ],
                cwd=native / "runtime/bin/linux-x86",
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            try:
                for _ in range(100):
                    text = "\n".join(
                        p.read_text(errors="replace")
                        for p in root.rglob("*")
                        if p.is_file() and (p.suffix in (".txt", ".log"))
                    )
                    failures = [
                        line for line in text.splitlines() if "RW_TEST_FAIL" in line
                    ]
                    if failures:
                        raise AssertionError("\n".join(failures))
                    if "RW_TEST_PASS conversation routing" in text:
                        assert "Loaded plugin" in text and "NWNX_Player.so" in text
                        print(
                            "PASS native merchant admin: catalogue, custom rules, quantity bounds, clone add/remove, stale/concurrent refusal, persisted stock and interrupted edit rollback"
                        )
                        print(
                            "\n".join(
                                line
                                for line in text.splitlines()
                                if "RW_CATALOG " in line
                            )
                        )
                        print(
                            "PASS native haggling: percentage boundaries, whole-gold prices, cached retries, customer isolation, failed attempts and expiry"
                        )
                        print(
                            "PASS native merchant/lead: five weapons, positive prices, finite depletion, campaign restore, stock snapshot, non-player refusal, lead wait/resume and home destination"
                        )
                        print(
                            "\n".join(
                                line
                                for line in text.splitlines()
                                if "RW_SHOP_ITEM " in line
                            )
                        )
                        check_transport(prefix)
                        print(
                            "PASS native routing: independent participants, direct addressing, ambiguity, range, expiry, control/session changes, hook restoration"
                        )
                        return
                    if process.poll() is not None:
                        raise RuntimeError("Test server exited")
                    time.sleep(0.25)
                raise AssertionError("No native test completion marker")
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()


if __name__ == "__main__":
    main()
