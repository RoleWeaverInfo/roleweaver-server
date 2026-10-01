// Demo-only rescue facts and one-time reward. Never infer success from player speech.
#include "rq_inc"
#include "rq_relations"
int RQDefeated(object npc)
{
 return GetIsObjectValid(npc) && (GetIsDead(npc) || (GetLocalString(npc,"rw_combat_phase")=="withdrawn" && GetLocalString(npc,"rw_combat_reason")=="low_health"));
}
void main()
{
 object m=GetModule(),a=RWFind("morga"),b=RWFind("grust"),e=RWFind("elana_voss");
 // Dedicated non-global factions prevent a fight with the trolls changing civilian reputation.
 if(GetIsObjectValid(a) && NWNX_Creature_GetFaction(a)!=5)NWNX_Creature_SetFaction(a,5);
 if(GetIsObjectValid(b) && NWNX_Creature_GetFaction(b)!=5)NWNX_Creature_SetFaction(b,5);
 if(GetIsObjectValid(e) && NWNX_Creature_GetFaction(e)!=6)NWNX_Creature_SetFaction(e,6);
 object r=RWFind("road_robber");if(GetIsObjectValid(r) && NWNX_Creature_GetFaction(r)!=7)NWNX_Creature_SetFaction(r,7);
 if(GetIsObjectValid(e) && !GetIsDead(e) && !GetIsDMPossessed(e) && GetLocalString(e,"rw_mode")=="auto")
 {
  string token=GetLocalString(a,"rw_enc_token");
  if(token!="" && token!=GetLocalString(e,"rq_rescue_token"))
  {
   SetLocalString(e,"rq_rescue_token",token);DeleteLocalInt(e,"rq_released");DeleteLocalInt(e,"rq_frightened");DeleteLocalInt(e,"rq_ransom_paid");DeleteLocalInt(e,"rq_escort_started");DeleteLocalObject(e,"rq_rescuer");DeleteLocalInt(e,"rq_morga_defeated");DeleteLocalInt(e,"rq_grust_defeated");
  }
  // Remember verified defeats for this activation, even after corpses disappear.
  if(RQDefeated(a))SetLocalInt(e,"rq_morga_defeated",TRUE);
  if(RQDefeated(b))SetLocalInt(e,"rq_grust_defeated",TRUE);
  object observer=GetFirstPC();
  while(GetIsObjectValid(observer)){RQCaptiveRelation(e,observer,TRUE);observer=GetNextPC();}
  RQCaptiveRelation(e,a,FALSE);
  RQCaptiveRelation(e,b,FALSE);
  if(GetIsInCombat(e))AssignCommand(e,ClearAllActions(TRUE));
  object pc=GetLocalObject(e,"rq_rescuer");
  if(!GetIsObjectValid(pc) && GetIsObjectValid(a))pc=GetLocalObject(a,"rw_enc_target");
  if(GetIsPC(pc) && !GetIsDM(pc) && !GetIsDead(pc))
  {
   SetLocalObject(e,"rq_rescuer",pc);
   int fighting=(GetIsObjectValid(a) && !GetIsDead(a) && GetIsInCombat(a)) || (GetIsObjectValid(b) && !GetIsDead(b) && GetIsInCombat(b));
   if(fighting && !GetLocalInt(e,"rq_frightened"))
   {SetLocalInt(e,"rq_frightened",1);RQSay(pc,e,"Please, stop! I don't want anyone else hurt! *She backs away, trembling.*");}
   if(!GetLocalInt(e,"rq_released") && !fighting && (GetLocalInt(e,"rq_ransom_paid") || (GetLocalInt(e,"rq_morga_defeated")&&GetLocalInt(e,"rq_grust_defeated"))))
   {
    SetLocalInt(e,"rq_released",1);SetLocalObject(e,"rq_rescuer",pc);
    RQCaptiveRelation(e,pc,TRUE);AssignCommand(e,ClearAllActions(TRUE));
    RQSay(pc,e,"Thank you. I thought I would never leave this place. Please, take me out of this cave. I'll follow you.");
   }
   // NPCs do not use PC door transitions automatically. Cross only this real,
   // linked cave exit when both escort partners reached its opposite sides.
   if(GetLocalInt(e,"rq_released") && GetLocalObject(e,"rq_rescuer")==pc && GetLocalInt(e,"rq_escort_started") && GetResRef(GetArea(e))=="rw_cave" && GetArea(pc)!=GetArea(e)
      && GetLocalString(e,"rw_action_kind")=="follow" && (GetLocalString(e,"rw_action_status")=="running" || GetLocalString(e,"rw_action_status")=="player unavailable"))
   {
    object door=GetFirstObjectInArea(GetArea(e));
    while(GetIsObjectValid(door))
    {
     if(GetObjectType(door)==OBJECT_TYPE_DOOR && GetDistanceBetween(e,door)<=6.0)
     {
      object exit=GetTransitionTarget(door);
      if(GetIsObjectValid(exit) && GetArea(exit)==GetArea(pc) && GetDistanceBetween(exit,pc)<=10.0)
      {AssignCommand(e,ClearAllActions(TRUE));AssignCommand(e,JumpToLocation(GetLocation(exit)));SetLocalString(e,"rw_action_status","completed");break;}
     }
     door=GetNextObjectInArea(GetArea(e));
    }
   }
   if(GetLocalInt(e,"rq_released") && GetLocalObject(e,"rq_rescuer")==pc && GetArea(pc)==GetArea(e) && GetDistanceBetween(pc,e)<=4.0 && !GetIsInCombat(e))
   {
    if(!GetLocalInt(e,"rq_ransom_paid") && !GetCampaignInt("rw_demo_rescue","elana_reward_v1",pc))
    {
     SetCampaignInt("rw_demo_rescue","elana_reward_v1",1,pc);
     GiveGoldToCreature(pc,100);ExportSingleCharacter(pc);
     RQSay(pc,e,"I kept these hundred gold hidden from them. Please take them, with my thanks.");
    }
    if(!GetLocalInt(e,"rq_escort_started"))
    {
     SetLocalInt(e,"rq_escort_started",1);SetLocalObject(e,"rw_action_player",pc);
     SetLocalString(e,"rw_action_kind","follow");SetLocalString(e,"rw_action_status","running");
     SetLocalInt(e,"rw_action_epoch",GetLocalInt(e,"rw_epoch"));SetLocalInt(e,"rw_action_deadline",GetLocalInt(m,"rw_tick")+120);
    }
   }
  }
 }
 DelayCommand(1.0,ExecuteScript("rq_rescue",m));
}
