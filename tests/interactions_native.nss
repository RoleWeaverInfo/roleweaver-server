// Disposable native test: no players or live services required.
#include "rw_actions"
#include "rw_npcfight"
void Check(int ok,string name){WriteTimestampedLogEntry("RW_INV_TEST "+name+" "+(ok?"PASS":"FAIL"));}
void main()
{
 object area=GetArea(GetObjectByTag("rq_testchest"));location l=Location(area,Vector(30.34,24.55,0.0),0.0);
 object payer=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",l),recipient=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",l);
 SetEventScript(payer,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");SetEventScript(recipient,EVENT_SCRIPT_CREATURE_ON_HEARTBEAT,"");
 GiveGoldToCreature(payer,100);int a=GetGold(payer),b=GetGold(recipient);
 Check(RWTransferPayment(payer,recipient,25) && GetGold(payer)==a-25 && GetGold(recipient)==b+25,"gold_conserved");
 a=GetGold(payer);b=GetGold(recipient);
 Check(!RWTransferPayment(payer,recipient,a+1) && GetGold(payer)==a && GetGold(recipient)==b,"insufficient_funds_unchanged");
 Check(!RWTransferPayment(payer,recipient,0) && !RWTransferPayment(payer,payer,1),"invalid_transfer_rejected");
 Check(!RWPaymentPlayer(payer,recipient),"npc_cannot_consent_as_player");
 RWPaymentConfirm(payer,"invalid");Check(GetGold(payer)==a && GetGold(recipient)==b,"missing_consent_no_transfer");
 SetLocalString(payer,"rw_id","payer");SetLocalString(recipient,"rw_id","recipient");
 SetLocalString(payer,"rw_mode","auto");SetLocalString(recipient,"rw_mode","auto");
 SetLocalInt(recipient,"rw_interaction_enabled",TRUE);SetLocalInt(recipient,"rw_interaction_lease",105);
 SetLocalString(recipient,"rw_interaction_revision","123456789012345678901234");SetLocalInt(GetModule(),"rw_tick",100);
 json policy=JsonParse("{\"enabled\":true,\"any_target\":true,\"targets\":[]}");
 SetLocalString(recipient,"rw_npcfight_policy","{\"allow_targeted\":false}");
 Check(!RWNPCFightAllowed(payer,recipient,policy),"target_must_opt_in");
 SetLocalString(recipient,"rw_npcfight_policy","{\"allow_targeted\":true}");
 Check(RWNPCFightAllowed(payer,recipient,policy),"permitted_target_available");
 SetLocalInt(GetModule(),"rw_tick",106);
 Check(!RWNPCFightAllowed(payer,recipient,policy),"expired_permission_lease_rejected");
 WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
