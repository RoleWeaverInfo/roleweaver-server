// Explicit, expiring player consent. No LLM text can debit gold.
#include "rw_inc"
int RWInteractionSetup(object npc,json cmd)
{
 if(RWS(cmd,"world")!=RWWorld() || GetStringLength(RWS(cmd,"revision"))!=24)return FALSE;
 json pay=JsonObjectGet(cmd,"payment"),fight=JsonObjectGet(cmd,"npc_combat");
 if(RWI(pay,"minimum")<1 || RWI(pay,"amount")<RWI(pay,"minimum") || RWI(pay,"amount")>100000
  || RWI(fight,"radius")<1 || RWI(fight,"radius")>40 || RWI(fight,"leash")<2 || RWI(fight,"leash")>60
  || RWI(fight,"retreat_hp")<0 || RWI(fight,"retreat_hp")>90 || JsonGetLength(JsonObjectGet(fight,"targets"))>100)return FALSE;
 SetLocalInt(npc,"rw_interaction_enabled",JsonDump(JsonObjectGet(cmd,"enabled"))=="true");
 SetLocalString(npc,"rw_interaction_revision",RWS(cmd,"revision"));
 SetLocalString(npc,"rw_payment_policy",JsonDump(pay));
 SetLocalString(npc,"rw_npcfight_policy",JsonDump(fight));
 SetLocalInt(npc,"rw_interaction_lease",GetLocalInt(GetModule(),"rw_tick")+5);
 return TRUE;
}
int RWInteractionReady(object npc,string revision)
{
 return GetIsObjectValid(npc) && !GetIsPC(npc) && !GetIsDead(npc) && !GetIsDMPossessed(npc)
  && GetLocalString(npc,"rw_id")!="" && GetLocalString(npc,"rw_mode")=="auto"
  && GetLocalInt(npc,"rw_interaction_enabled") && revision==GetLocalString(npc,"rw_interaction_revision")
  && GetLocalInt(GetModule(),"rw_tick")<=GetLocalInt(npc,"rw_interaction_lease");
}
int RWPaymentPlayer(object pc,object npc)
{
 return GetIsObjectValid(pc) && GetIsPC(pc) && !GetIsDM(pc) && !GetIsDMPossessed(pc) && !GetIsDead(pc)
  && !GetIsInCombat(pc) && !GetIsInCombat(npc) && GetArea(pc)==GetArea(npc)
  && GetDistanceBetween(pc,npc)<=3.0 && LineOfSightObject(pc,npc);
}
// A window binds this offer ID, so an old button cannot accept new terms.
int RWPaymentPending(object npc,object pc)
{
 return GetLocalString(pc,"rw_pay_offer")!="" && GetLocalObject(pc,"rw_pay_npc")==npc
  && RWInteractionReady(npc,GetLocalString(pc,"rw_pay_revision")) && RWPaymentPlayer(pc,npc)
  && GetLocalInt(pc,"rw_pay_epoch")==GetLocalInt(npc,"rw_epoch")
  && GetLocalInt(GetModule(),"rw_tick")<=GetLocalInt(pc,"rw_pay_until");
}
int RWPaymentOffer(object npc,json cmd)
{
 json p=JsonParse(GetLocalString(npc,"rw_payment_policy"));
 object pc=StringToObject(RWS(cmd,"listener"));int amount=RWI(cmd,"amount");
 if(RWS(cmd,"world")!=RWWorld() || !RWInteractionReady(npc,RWS(cmd,"revision"))
  || JsonDump(JsonObjectGet(p,"enabled"))!="true" || !RWPaymentPlayer(pc,npc)
  || amount<RWI(p,"minimum") || amount>RWI(p,"amount") || GetStringLength(RWS(cmd,"offer"))!=24)return FALSE;
 // One outstanding offer per player. A new offer replaces the old offer.
 SetLocalObject(pc,"rw_pay_npc",npc);SetLocalInt(pc,"rw_pay_epoch",GetLocalInt(npc,"rw_epoch"));
 SetLocalInt(pc,"rw_pay_amount",amount);SetLocalString(pc,"rw_pay_offer",RWS(cmd,"offer"));
 SetLocalString(pc,"rw_pay_revision",RWS(cmd,"revision"));SetLocalInt(pc,"rw_pay_until",GetLocalInt(GetModule(),"rw_tick")+120);

 return TRUE;
}
// Runs synchronously on the game thread after all consent and balance checks.
// Never retried by the companion. World save scripts still own crash persistence.
int RWTransferPayment(object payer,object recipient,int amount)
{
 if(!NWNX_Core_PluginExists("NWNX_Creature") || !GetIsObjectValid(payer) || !GetIsObjectValid(recipient)
  || amount<1 || amount>100000 || payer==recipient || GetGold(payer)<amount || GetGold(recipient)>2000000000-amount)return FALSE;
 int before=GetGold(payer),other=GetGold(recipient);
 NWNX_Creature_SetGold(payer,before-amount);
 if(GetGold(payer)!=before-amount)return FALSE;
 NWNX_Creature_SetGold(recipient,other+amount);
 if(GetGold(recipient)==other+amount)return TRUE;
 // A rejected credit must not leave the player debited.
 NWNX_Creature_SetGold(recipient,other);NWNX_Creature_SetGold(payer,before);
 return FALSE;
}
void RWPaymentConfirm(object pc,string expectedOffer)
{
 object npc=GetLocalObject(pc,"rw_pay_npc");string offer=GetLocalString(pc,"rw_pay_offer");
 if(offer=="" || expectedOffer!=offer || GetStringLength(expectedOffer)!=24)
 {SendMessageToPC(pc,"No matching pending payment. Ask for a fresh offer.");return;}
 if(!RWInteractionReady(npc,GetLocalString(pc,"rw_pay_revision")) || !RWPaymentPlayer(pc,npc)
  || GetLocalInt(npc,"rw_epoch")!=GetLocalInt(pc,"rw_pay_epoch")
  || GetLocalInt(GetModule(),"rw_tick")>GetLocalInt(pc,"rw_pay_until"))
 {DeleteLocalString(pc,"rw_pay_offer");SendMessageToPC(pc,"Payment expired or became unavailable. No gold taken.");return;}
 int amount=GetLocalInt(pc,"rw_pay_amount");
 if(GetGold(pc)<amount){SendMessageToPC(pc,"Not enough gold. No payment made.");return;}
 DeleteLocalString(pc,"rw_pay_offer"); // Consume consent before any mutation; duplicate hooks cannot pay twice.
 if(!RWTransferPayment(pc,npc,amount)){SendMessageToPC(pc,"Payment could not be confirmed. Contact the DM before retrying.");return;}
 ExportSingleCharacter(pc);
 json e=RWBase("payment_result",npc);
 e=JsonObjectSet(e,"offer",JsonString(offer));e=JsonObjectSet(e,"amount",JsonInt(amount));
 e=JsonObjectSet(e,"listener",JsonString(ObjectToString(pc)));
 e=JsonObjectSet(e,"payer",JsonString(GetPCPublicCDKey(pc)+":"+GetName(pc)));
 e=JsonObjectSet(e,"status",JsonString("paid"));RWEmit(e);
 SendMessageToPC(pc,"Payment confirmed: "+IntToString(amount)+" gold paid to "+GetName(npc)+".");
}
