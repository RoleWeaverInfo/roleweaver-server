// Opt-in AI-NPC combat. Never targets PCs or changes a global faction.
#include "rw_payment"
#include "rw_encounter"
int RWNPCFightAllowed(object npc,object target,json p)
{
 if(!GetIsObjectValid(target) || target==npc || GetIsPC(target) || GetIsDead(target) || GetIsDMPossessed(target)
  || GetLocalString(target,"rw_id")=="" || GetLocalString(target,"rw_mode")!="auto"
  || GetArea(target)!=GetArea(npc))return FALSE;
 json other=JsonParse(GetLocalString(target,"rw_npcfight_policy"));
 if(JsonDump(JsonObjectGet(p,"enabled"))!="true" || JsonDump(JsonObjectGet(other,"allow_targeted"))!="true"
  || !RWInteractionReady(target,GetLocalString(target,"rw_interaction_revision")))return FALSE;
 if(JsonDump(JsonObjectGet(p,"any_target"))=="true")return TRUE;
 json allowed=JsonObjectGet(p,"targets");int i;
 for(i=0;i<JsonGetLength(allowed);i++)if(JsonGetString(JsonArrayGet(allowed,i))==GetLocalString(target,"rw_id"))return TRUE;
 return FALSE;
}
int RWNPCStartFight(object npc,json cmd)
{
 object target=RWFind(RWS(cmd,"target"));json p=JsonParse(GetLocalString(npc,"rw_npcfight_policy"));
 if(RWS(cmd,"world")!=RWWorld() || !RWInteractionReady(npc,RWS(cmd,"revision")) || !RWNPCFightAllowed(npc,target,p)
  || RWI(cmd,"target_epoch")!=GetLocalInt(target,"rw_epoch")
  || RWS(cmd,"target_revision")!=GetLocalString(target,"rw_interaction_revision")
  || GetDistanceBetween(npc,target)>IntToFloat(RWI(p,"radius")) || !LineOfSightObject(npc,target) || !GetObjectSeen(target,npc)
  || RWS(cmd,"request")==GetLocalString(npc,"rw_npcfight_request"))return FALSE;
 RWCombatRelease(npc);
 SetLocalString(npc,"rw_npcfight_request",RWS(cmd,"request"));
 SetLocalInt(npc,"rw_combat_active",TRUE);SetLocalInt(npc,"rw_combat_target_npc",TRUE);
 SetLocalObject(npc,"rw_combat_target",target);SetLocalInt(npc,"rw_combat_epoch",GetLocalInt(npc,"rw_epoch"));
 SetLocalInt(npc,"rw_npcfight_target_epoch",GetLocalInt(target,"rw_epoch"));
 SetLocalInt(npc,"rw_combat_leash",RWI(p,"leash"));SetLocalInt(npc,"rw_combat_hp",RWI(p,"retreat_hp"));
 SetLocalLocation(npc,"rw_combat_home",GetLocation(npc));SetLocalLocation(npc,"rw_combat_anchor",GetLocation(npc));
 SetLocalString(npc,"rw_combat_phase","fighting");
 DeleteLocalString(npc,"rw_combat_id");DeleteLocalString(npc,"rw_combat_token");
 DeleteLocalInt(npc,"rw_combat_return_reported");DeleteLocalString(npc,"rw_combat_reason");
 SetLocalString(npc,"rw_action_status","interrupted");
 SetIsTemporaryEnemy(target,npc,TRUE,6.0);
 AssignCommand(npc,ClearAllActions(TRUE));AssignCommand(npc,ActionAttack(target));
 return TRUE;
}
void RWNPCFightTick(object npc)
{
 if(!GetLocalInt(npc,"rw_combat_active") || !GetLocalInt(npc,"rw_combat_target_npc"))return;
 object target=GetLocalObject(npc,"rw_combat_target");json p=JsonParse(GetLocalString(npc,"rw_npcfight_policy"));
 if(GetLocalString(npc,"rw_combat_phase")!="fighting")return;
 if(!RWInteractionReady(npc,GetLocalString(npc,"rw_interaction_revision"))
  || !RWNPCFightAllowed(npc,target,p) || GetLocalInt(target,"rw_epoch")!=GetLocalInt(npc,"rw_npcfight_target_epoch"))
 {RWCombatReturn(npc,"target_gone");return;}
 SetIsTemporaryEnemy(target,npc,TRUE,6.0);
}
