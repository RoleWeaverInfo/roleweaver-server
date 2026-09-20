#include "rq_inc"
void main()
{
 object king=OBJECT_SELF;if(!GetIsObjectValid(king))return;
 int tick=GetLocalInt(GetModule(),"rw_tick");
 object pc=GetFirstPC();int talking=FALSE;
 while(GetIsObjectValid(pc)){if(RWCurrentTalk(pc)==king)talking=TRUE;pc=GetNextPC();}
 if(talking||GetIsDMPossessed(king)||GetCurrentAction(king)==ACTION_DIALOGOBJECT)SetLocalInt(king,"rq_last",tick);
 if(tick-GetLocalInt(king,"rq_last")<180){DelayCommand(10.0,ExecuteScript("rq_royal",king));return;}
 RWMode(king,"paused");AssignCommand(king,ClearAllActions());
 string farewell="The audience is concluded. Captain Beran can arrange another when needed.";
 RQSay(OBJECT_INVALID,king,farewell);
 pc=GetFirstPC();
 while(GetIsObjectValid(pc))
 {
  if(RWCanHear(pc,king,RWHearingRange()))SendMessageToPC(pc,GetName(king)+": "+farewell);
  pc=GetNextPC();
 }
 AssignCommand(king,ActionMoveToLocation(Location(GetArea(king),Vector(25.0,20.0,0.0),270.0),FALSE));
 int generation=GetLocalInt(GetModule(),"rq_audience_generation");
 AssignCommand(GetModule(),DelayCommand(15.0,RQFinishAudience(king,generation)));
}
