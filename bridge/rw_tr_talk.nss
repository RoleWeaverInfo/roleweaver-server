// OnConversation for the ordinary Royal Guide. No AI profile or binding required.
#include "rw_tr_dialog"
void main()
{
 if(GetListenPatternNumber()!=-1 || GetIsDead(OBJECT_SELF))return;
 object pc=GetLastSpeaker();
 if(GetIsPC(pc) && !GetIsDMPossessed(pc))RWTrDemoBegin(pc,OBJECT_SELF);
}
