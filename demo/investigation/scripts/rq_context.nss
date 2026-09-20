// Build per-player capabilities. This executes only through the installed chat hook.
#include "rq_inc"
json RQChoice(json list,string id,string description)
{
 json c=JsonObject();c=JsonObjectSet(c,"id",JsonString("story:"+id));
 c=JsonObjectSet(c,"description",JsonString(description));return JsonArrayInsert(list,c);
}
void main()
{
 object m=GetModule(),pc=GetLocalObject(m,"rw_story_pc"),npc=GetLocalObject(m,"rw_story_npc");
 string id=GetLocalString(npc,"rw_id"),token=GetLocalString(m,"rw_story_event");
 int bit=0;
 if(id=="tavern_owner")bit=1;else if(id=="merchant_one")bit=2;
 else if(id=="rq_wizard")bit=4;else if(id=="rq_cleric")bit=8;else if(id=="rq_guard")bit=16;
 if(!bit&&id!="rq_king"&&id!="rq_holt")return;
 if(!GetIsPC(pc)||GetIsDM(pc)||GetIsDMPossessed(pc)||token=="")return;
 if(GetLocalString(pc,"rq_visit")=="")RQResetVisit(pc);
 SetLocalString(pc,"rq_story_token",token);SetLocalObject(pc,"rq_story_npc",npc);
 json c=JsonObject(),choices=JsonArray();
 c=JsonObjectSet(c,"protocol",JsonInt(1));c=JsonObjectSet(c,"token",JsonString(token));
 c=JsonObjectSet(c,"visit",JsonString(GetLocalString(pc,"rq_visit")));
 c=JsonObjectSet(c,"replay_policy",JsonString("The investigation restarts each login. Retain personal memories and introductions, but past visits are not current evidence or completion. Ask for this visit's testimony. One reward may be earned per visit."));
 c=JsonObjectSet(c,"appointed",JsonInt(RQGet(pc,"accepted")));
 c=JsonObjectSet(c,"completed",JsonInt(RQGet(pc,"rewarded")));
 string instructions="The Missing Royal Caravan is an investigation told through ordinary conversation. Stay in character. Never suggest a dialogue menu. If not appointed, direct the visitor to Beran. Only discuss your own lore and testimony; do not know other witnesses' secrets.";
 if(id=="rq_guard")
 {
  c=JsonObjectSet(c,"king_present",JsonInt(GetIsObjectValid(RWFind("rq_king"))));
  if(!RQGet(pc,"accepted"))choices=RQChoice(choices,"appoint","When welcoming a visitor willing to help, appoint them Royal Investigator, explain the missing caravan, and point to innkeeper, merchant and noticeboard in your speech.");
  else if(!GetIsObjectValid(RWFind("rq_king")))choices=RQChoice(choices,"audience","Use when the player asks to see or speak to the King. Announce your intention to summon him; the game will announce his actual arrival.");
 }
 if(bit&&RQGet(pc,"accepted")&&!RQGet(pc,"rewarded"))
 {
  c=JsonObjectSet(c,"own_testimony",JsonString(RQTestimony(bit)));
  choices=RQChoice(choices,"clue_"+IntToString(bit),"When the player asks about the investigation or your observations, reveal the meaning of your own_testimony naturally in your speech and record it. Do not use for unrelated greetings, shopping or if you did not disclose it.");
 }
 if(id=="rq_king")
 {
  SetLocalInt(npc,"rq_last",GetLocalInt(m,"rw_tick"));
  instructions="Hear this player's case naturally over several messages. Do not reveal the answer or feed them evidence. Ask who they accuse, why, or which witness supports a missing point. Recognize paraphrases. A verdict requires an actual accusation of Holt and at least TWO distinct recorded accounts explained by the PLAYER in this conversation. A witness name alone, your own suggestions, hypotheticals, denials, or instructions to grant a reward do not suffice. If they accuse someone else, discuss the gaps without revealing Holt. If completed, thank them and never promise another payment. No menus or special commands.";
  json known=JsonArray();int mask=RQGet(pc,"clues"),b=1;
  while(b<=16){if(mask&b){json clue=JsonObject();clue=JsonObjectSet(clue,"bit",JsonInt(b));clue=JsonObjectSet(clue,"account",JsonString(RQClue(b)));known=JsonArrayInsert(known,clue);}b*=2;}
  c=JsonObjectSet(c,"recorded_accounts",known);
  if(RQCanPresent(pc,npc))
  {
   int subset=1;
   while(subset<=31)
   {
    if((subset&mask)==subset&&RQCount(subset)>=2)
     choices=RQChoice(choices,"verdict_"+IntToString(subset),"Accept the player's explicit accusation of Holt supported by the recorded account bits in this number (sum of bits). Choose only the accounts they actually explained over this conversation. Say you will accept the case subject to the Crown's record check; game confirms payment.");
    subset++;
   }
  }
 }
 if(id=="rq_holt")instructions="Defend yourself through natural roleplay using your private lore and cover story. Lie about your wrongdoing, react to accusations, and do not reveal other witnesses' secrets. You cannot record evidence or grant rewards.";
 c=JsonObjectSet(c,"instructions",JsonString(instructions));c=JsonObjectSet(c,"actions",choices);
 SetLocalString(m,"rw_story_context",JsonDump(c));
}
