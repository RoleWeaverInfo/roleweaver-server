// Apply an AI proposal only after speech passed safeguards and native delivery checks.
#include "rq_inc"
void main()
{
 object npc=OBJECT_SELF;
 json cmd=JsonParse(GetLocalString(npc,"rw_story_reply"));
 object pc=StringToObject(RWS(cmd,"listener"));string proposal=RWS(cmd,"story_action");
 if(!GetIsPC(pc)||GetIsDM(pc)||GetIsDMPossessed(pc)||GetIsDead(pc)
 ||GetIsDead(npc)||GetIsDMPossessed(npc)||GetLocalString(npc,"rw_mode")!="auto"
 ||GetArea(pc)!=GetArea(npc)||GetDistanceBetween(pc,npc)>10.0||!LineOfSightObject(pc,npc))return;
 // A newer player turn/target invalidates a delayed proposal. Consume once.
 if(RWS(cmd,"story_token")==""||RWS(cmd,"story_token")!=GetLocalString(pc,"rq_story_token")
 ||GetLocalObject(pc,"rq_story_npc")!=npc)return;
 DeleteLocalString(pc,"rq_story_token");
 string id=GetLocalString(npc,"rw_id");
 if(id=="rq_guard"&&proposal=="story:appoint"&&!RQGet(pc,"accepted"))
 {RQSet(pc,"accepted",1);SendMessageToPC(pc,"[Appointed Royal Investigator. Your notes are available with /case.]");return;}
 if(!RQGet(pc,"accepted"))return;
 if(id=="rq_guard"&&proposal=="story:audience"){RQAudience(pc,npc);return;}
 if(RQGet(pc,"rewarded"))return;
 int bit=0;
 if(id=="tavern_owner")bit=1;else if(id=="merchant_one")bit=2;else if(id=="rq_wizard")bit=4;
 else if(id=="rq_cleric")bit=8;else if(id=="rq_guard")bit=16;
 if(bit&&proposal=="story:clue_"+IntToString(bit))
 {
  int known=RQGet(pc,"clues");RQSet(pc,"clues",known|bit);
  if(!(known&bit))SendMessageToPC(pc,"[Witness account recorded. Use /case to review your notes.]");return;
 }
 if(id!="rq_king"||!RQCanPresent(pc,npc))return;
 int mask=RQVerdictMask(proposal,RQGet(pc,"clues"));if(!mask)return;
 RQSet(pc,"rewarded",1);GiveGoldToCreature(pc,100);ExportSingleCharacter(pc);
 RQSay(pc,npc,"The Crown accepts your case against Holt. For your service, you receive 100 gold. The investigation is complete.");
 WriteTimestampedLogEntry("ROLEWEAVER QUEST: conversation-led case accepted; visit reward issued.");
}
