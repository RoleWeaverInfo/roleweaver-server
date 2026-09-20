#include "rq_inc"
void main()
{
 object pc=GetEnteringObject();
 string previous=GetLocalString(GetModule(),"rq_previous_enter");
 if(previous!=""&&previous!="rq_enter")ExecuteScript(previous,GetModule());
 if(!GetIsPC(pc)||GetIsDM(pc)||GetIsDMPossessed(pc))return;
 RQResetVisit(pc);
 SendMessageToPC(pc,"[A fresh investigation begins for this visit. NPCs still remember you. Speak to Captain Beran to begin.]");
}
