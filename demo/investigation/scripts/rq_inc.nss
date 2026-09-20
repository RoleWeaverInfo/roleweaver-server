// Demo story authority. AI proposals are verified by rq_reply before changing progress.
#include "rw_chat_inc"
int RQHas(string s,string word){return FindSubString(s,word)>=0;}
// Spoken testimony is public nearby chat; the addressed player's server log
// also receives a copy. Hearing it does not award another player's clue.
void RQSay(object pc, object npc, string words)
{
 if (!GetIsObjectValid(npc)) return;
 NWNX_Chat_SendMessage(NWNX_CHAT_CHANNEL_PLAYER_TALK, words, npc);
 if (GetIsPC(pc)) SendMessageToPC(pc, GetName(npc) + ": " + words);
}
string RQWords(string line)
{
 line = GetStringLowerCase(line);
 string result = " ";
 int i;
 for (i = 0; i < GetStringLength(line); i++)
 {
  string c = GetSubString(line, i, 1);
  if (FindSubString("abcdefghijklmnopqrstuvwxyz", c) >= 0) result += c;
  else if (GetStringRight(result, 1) != " ") result += " ";
 }
 return result + " ";
}
int RQWord(string words, string word) { return RQHas(words, " " + word + " "); }
int RQAudienceRequest(string line)
{
 string w = RQWords(line);
 // A refusal or cancellation must not become a summons.
 if (RQWord(w,"not") || RQWord(w,"never") || RQWord(w,"cancel")
     || RQWord(w,"dont") || RQHas(w," don t ")) return FALSE;
 if (RQWord(w,"audience")) return TRUE;
 if (!RQWord(w,"king") && !RQWord(w,"majesty")) return FALSE;
 return RQWord(w,"call") || RQWord(w,"summon") || RQWord(w,"bring")
     || RQWord(w,"fetch") || RQWord(w,"see") || RQWord(w,"meet")
     || RQWord(w,"speak") || RQWord(w,"talk") || RQWord(w,"invite");
}
// Investigation progress belongs to this login, never to persistent NPC memory.
void RQResetVisit(object pc)
{
 DeleteLocalInt(pc,"rq_run_accepted");DeleteLocalInt(pc,"rq_run_clues");DeleteLocalInt(pc,"rq_run_rewarded");
 DeleteLocalString(pc,"rq_story_token");DeleteLocalObject(pc,"rq_story_npc");
 object m=GetModule();int serial=GetLocalInt(m,"rq_visit_serial")+1;
 SetLocalInt(m,"rq_visit_serial",serial);
 SetLocalString(pc,"rq_visit",GetLocalString(m,"rw_session")+":visit:"+IntToString(serial));
}
int RQGet(object pc,string key){return GetLocalInt(pc,"rq_run_"+key);}
void RQSet(object pc,string key,int value){SetLocalInt(pc,"rq_run_"+key,value);}
int RQCount(int mask){int n=0;while(mask>0){n+=mask%2;mask=mask/2;}return n;}
string RQClue(int bit)
{
 if(bit==1)return "Innkeeper: the strangers wore military equipment beneath travelling cloaks.";
 if(bit==2)return "Merchant: Holt signed the order changing the caravan's route.";
 if(bit==4)return "Wizard: the sealed chest was the target; he had privately briefed Holt about its magical contents.";
 if(bit==8)return "Cleric: the wounded escort heard, 'Holt wants the sealed chest intact.'";
 return "Guard: the attackers knew the royal supply password, available to quartermaster staff.";
}
string RQTestimony(int bit)
{
 if(bit==1)return "I saw the strangers wearing military equipment beneath their travelling cloaks.";
 if(bit==2)return "I saw the order changing the caravan's route. It bore Quartermaster Holt's signature.";
 if(bit==4)return "The sealed magical chest was the target. I had privately briefed Holt about its contents.";
 if(bit==8)return "The wounded escort I treated heard the attackers say, 'Holt wants the sealed chest intact.'";
 return "The attackers knew the royal supply password. Quartermaster staff had access to it.";
}
void RQNotes(object pc)
{
 SendMessageToPC(pc,"ROYAL INVESTIGATOR - THE MISSING CARAVAN");
 if(!RQGet(pc,"accepted")){SendMessageToPC(pc,"Speak to Captain Beran near the entrance about your duty.");return;}
 int mask=RQGet(pc,"clues"),bit=1;
 while(bit<=16){if(mask & bit)SendMessageToPC(pc,RQClue(bit));bit*=2;}
 if(!mask)SendMessageToPC(pc,"No witness statements recorded. Begin with the innkeeper and merchant.");
 if(RQGet(pc,"rewarded"))SendMessageToPC(pc,"Case solved. The Crown has already awarded 100 gold during this visit.");
 else SendMessageToPC(pc,"Ask the guard for an audience when ready. Accuse a suspect and cite two recorded clues to the King.");
}
int RQCanPresent(object pc,object king)
{
 return GetIsPC(pc)&&!GetIsDM(pc)&&!GetIsDMPossessed(pc)&&GetIsObjectValid(king)
 &&GetLocalString(king,"rw_id")=="rq_king"&&!GetIsDMPossessed(king)
 &&GetLocalString(king,"rw_mode")=="auto"&&GetArea(pc)==GetArea(king)
 &&GetDistanceBetween(pc,king)<=10.0&&LineOfSightObject(pc,king)
 &&RQGet(pc,"accepted")&&!RQGet(pc,"rewarded");
}
// Run delayed departure on the module, which survives the King's destruction.
// A generation check prevents an old timer from clearing a newer audience.
void RQFinishAudience(object king,int generation)
{
 object m=GetModule();
 if(GetLocalInt(m,"rq_audience_generation")!=generation)return;
 if(GetIsObjectValid(king)&&GetIsDMPossessed(king))
 {DelayCommand(5.0,RQFinishAudience(king,generation));return;}
 DeleteLocalInt(m,"rq_audience_busy");
 if(GetIsObjectValid(king))DestroyObject(king);
}
void RQAudience(object pc,object guard)
{
 if(GetIsObjectValid(RWFind("rq_king"))){RQSay(pc,guard,"The King is already in the hall. Approach the throne and address him as King.");return;}
 // A missing King means any old busy flag is stale. NPC creation is synchronous.
 DeleteLocalInt(GetModule(),"rq_audience_busy");
 object throne=GetObjectByTag("rq_throne");
 if(!GetIsObjectValid(throne)){RQSay(pc,guard,"The throne is unavailable; please report this to the server owner.");return;}
 object king=CreateObject(OBJECT_TYPE_CREATURE,"rq_king",Location(GetArea(guard),Vector(25.0,20.0,0.0),90.0));
 if(!GetIsObjectValid(king))
 {
  RQSay(pc,guard,"I could not arrange the King's arrival. Please report this to the server owner.");
  WriteTimestampedLogEntry("ROLEWEAVER QUEST: failed to create rq_king.");
  return;
 }
 SetLocalInt(GetModule(),"rq_audience_busy",TRUE);
 SetLocalInt(GetModule(),"rq_audience_generation",GetLocalInt(GetModule(),"rq_audience_generation")+1);
 SetAILevel(king,AI_LEVEL_VERY_HIGH);
 SetLocalString(king,"rw_source","world");RWBind(king,"rq_king",OBJECT_INVALID);RWMode(king,"auto");
 RQSay(pc,guard,"Make way for the King of Role Weaver! The Crown will hear the Royal Investigator.");
 AssignCommand(king,ActionMoveToObject(throne,FALSE,1.5));
 AssignCommand(king,ActionSit(throne));
 SetLocalInt(king,"rq_last",GetLocalInt(GetModule(),"rw_tick"));
 DelayCommand(10.0,ExecuteScript("rq_royal",king));
}

// Pure validation shared by the live commit path and native regression checks.
int RQVerdictMask(string proposal,int known)
{
 if(GetStringLeft(proposal,14)!="story:verdict_")return 0;
 int mask=StringToInt(GetSubString(proposal,14,3));
 if(proposal!="story:verdict_"+IntToString(mask)||mask<1||mask>31
 ||(mask&known)!=mask||RQCount(mask)<2)return 0;
 return mask;
}
