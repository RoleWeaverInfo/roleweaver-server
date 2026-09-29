#include "rw_tr_dialog"
#include "nwnx_events"
void main()
{
 if(NWNX_Events_GetCurrentEvent()=="NWNX_ON_EXAMINE_OBJECT_BEFORE")
  RWTrExamine(OBJECT_SELF,StringToObject(NWNX_Events_GetEventData("EXAMINEE_OBJECT_ID")));
 if(NWNX_Events_GetCurrentEvent()=="NWNX_ON_CLIENT_DISCONNECT_BEFORE")
 {RWTrClearNames(OBJECT_SELF);RWTrDlgFinish(OBJECT_SELF);}
}
