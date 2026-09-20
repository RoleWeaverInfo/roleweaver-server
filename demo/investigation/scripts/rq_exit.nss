#include "rq_inc"
void main()
{
 object pc=GetExitingObject();
 if(GetIsPC(pc)&&!GetIsDM(pc)&&!GetIsDMPossessed(pc))RQResetVisit(pc);
 string previous=GetLocalString(GetModule(),"rq_previous_exit");
 if(previous!=""&&previous!="rq_exit")ExecuteScript(previous,GetModule());
}
