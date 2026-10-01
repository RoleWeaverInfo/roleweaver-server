// Called only after the bridge has verified and completed a gold transfer.
#include "rq_inc"
void main()
{
 object m=GetModule(),npc=GetLocalObject(m,"rw_paid_npc"),pc=GetLocalObject(m,"rw_paid_pc");
 int amount=GetLocalInt(m,"rw_paid_amount");object e=RWFind("elana_voss");
 if(GetLocalString(npc,"rw_id")!="morga" || amount<75 || amount>100 || !GetIsPC(pc) || !GetIsObjectValid(e) || GetIsDead(e))return;
 SetLocalInt(e,"rq_ransom_paid",1);SetLocalObject(e,"rq_rescuer",pc);
}
