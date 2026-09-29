// Optional standard NWN dialogue fixture. Branches are authored, never chosen by an LLM.
#include "rw_translate"
#include "rw_tr_demo"

void RWTrDlgRelease(object npc)
{
 if(!GetIsObjectValid(npc) || !GetLocalInt(npc,"rw_tr_demo_lock"))return;
 if(GetLocalInt(npc,"rw_tr_demo_ai") && !GetIsDMPossessed(npc) && GetLocalInt(npc,"rw_epoch")==GetLocalInt(npc,"rw_tr_demo_epoch")
   && GetLocalString(npc,"rw_mode")=="paused")RWMode(npc,GetLocalString(npc,"rw_tr_demo_mode"));
 DeleteLocalInt(npc,"rw_tr_demo_lock");DeleteLocalObject(npc,"rw_tr_demo_pc");DeleteLocalInt(npc,"rw_tr_demo_ai");
}
void RWTrDlgFinish(object pc)
{
 object npc=GetLocalObject(pc,"rw_tr_dialog_npc");
 // A delayed end/abort callback must never release another player's conversation.
 if(GetLocalObject(npc,"rw_tr_demo_pc")==pc)RWTrDlgRelease(npc);
 DeleteLocalInt(pc,"rw_tr_dialog_active");DeleteLocalInt(pc,"rw_tr_dialog_pending");
 DeleteLocalObject(pc,"rw_tr_dialog_npc");
}
void RWTrDlgWatch(object npc)
{
 if(!GetLocalInt(npc,"rw_tr_demo_lock") || GetLocalInt(npc,"rw_tr_demo_deadline")>GetLocalInt(GetModule(),"rw_tick"))return;
 object pc=GetLocalObject(npc,"rw_tr_demo_pc");
 if(!GetIsPC(pc) || !IsInConversation(npc))
 {if(GetIsObjectValid(pc))RWTrDlgFinish(pc);else RWTrDlgRelease(npc);}
}
// ActionStartConversation fires OnDialogue again. On an AI NPC that handler
// selects free-form chat instead of opening the DLG. Begin the authored tree
// directly in the NPC's context, as a standard OnDialogue script does.
void RWTrDlgStart(object pc)
{
 if(!BeginConversation(RW_TR_DEMO_RESREF,pc))
 {
  RWTrDlgFinish(pc);
  WriteTimestampedLogEntry("Role Weaver: BeginConversation failed for rw_tr_demo. Check the dialogue resource and conversation state.");
  SendMessageToPC(pc,"NWN could not open the test dialogue. Please report this to the server administrator.");
 }
}
void RWTrDlgOpen(object pc)
{
 object npc=GetLocalObject(pc,"rw_tr_dialog_npc");
 DeleteLocalInt(pc,"rw_tr_dialog_pending");
 if(!GetIsPC(pc) || !GetIsObjectValid(npc) || GetIsPC(npc) || GetLocalString(npc,"rw_mode")=="dm" || GetArea(pc)!=GetArea(npc)
  || GetDistanceBetween(pc,npc)>6.0 || GetIsInCombat(pc) || GetIsInCombat(npc)
  || GetIsDMPossessed(npc) || GetLocalInt(npc,"rw_no_translate") || GetLocalInt(npc,"rw_tr_demo_lock") || IsInConversation(pc) || IsInConversation(npc))return;
 RWEndTalk(pc);
 // Ordinary module NPCs have no Role Weaver profile or mode to change.
 int ai=GetLocalString(npc,"rw_id")!="";SetLocalInt(npc,"rw_tr_demo_ai",ai);
 if(ai)
 {
  SetLocalString(npc,"rw_tr_demo_mode",GetLocalString(npc,"rw_mode"));
  RWMode(npc,"paused");SetLocalInt(npc,"rw_tr_demo_epoch",GetLocalInt(npc,"rw_epoch"));
 }
 SetLocalInt(npc,"rw_tr_demo_lock",TRUE);SetLocalObject(npc,"rw_tr_demo_pc",pc);
 SetLocalInt(npc,"rw_tr_demo_deadline",GetLocalInt(GetModule(),"rw_tick")+3);
 SetLocalInt(pc,"rw_tr_dialog_active",TRUE);
 AssignCommand(npc,ClearAllActions(TRUE));
 AssignCommand(npc,RWTrDlgStart(pc));
}
void RWTrDemoBegin(object pc,object selected=OBJECT_INVALID)
{
 if(!GetIsPC(pc) || GetIsDMPossessed(pc) || !NWNX_Core_PluginExists("NWNX_Player"))return;
 if(IsInConversation(pc) || GetIsInCombat(pc) || GetLocalInt(pc,"rw_tr_dialog_pending"))return;
 object npc=selected;float closest=6.0;
 if(!GetIsObjectValid(npc))npc=RWCurrentTalk(pc);
 if(!GetIsObjectValid(npc) || GetArea(pc)!=GetArea(npc) || GetDistanceBetween(pc,npc)>closest)
 {
  npc=OBJECT_INVALID;int i,count=GetLocalInt(GetModule(),"rw_count");
  for(i=0;i<count;i++)
  {
   object candidate=GetLocalObject(GetModule(),"rw_slot_"+IntToString(i));
   if(GetIsObjectValid(candidate) && GetArea(candidate)==GetArea(pc) && !GetIsPC(candidate)
      && !GetIsDMPossessed(candidate) && GetDistanceBetween(pc,candidate)<=closest)
   {npc=candidate;closest=GetDistanceBetween(pc,candidate);}
  }
 }
 if(!GetIsObjectValid(npc) || GetIsPC(npc) || GetLocalString(npc,"rw_mode")=="dm" || IsInConversation(npc) || GetIsInCombat(npc)
   || GetIsDMPossessed(npc) || GetLocalInt(npc,"rw_no_translate") || GetLocalInt(npc,"rw_tr_demo_lock"))
 {SendMessageToPC(pc,"Speak to the Royal Guide near the hall entrance, or select an available AI NPC within 6 metres and type /rw dialogue.");return;}
 SetLocalObject(pc,"rw_tr_dialog_npc",npc);
 // Begin normally. Prepared conditions request only reached lines/choices;
 // opening this conversation must never enqueue its entire nine-node tree.
 RWTrDlgOpen(pc);
}
