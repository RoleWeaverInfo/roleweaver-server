#include "rw_inc"
void main(){
 object rq_guard=GetObjectByTag("rq_guard");
 if(GetIsObjectValid(rq_guard) && !GetIsObjectValid(RWFind("rq_guard"))){SetLocalString(rq_guard,"rw_source","world");RWBind(rq_guard,"rq_guard",OBJECT_INVALID);RWMode(rq_guard,"auto");}
 object rq_wizard=GetObjectByTag("rq_wizard");
 if(GetIsObjectValid(rq_wizard) && !GetIsObjectValid(RWFind("rq_wizard"))){SetLocalString(rq_wizard,"rw_source","world");RWBind(rq_wizard,"rq_wizard",OBJECT_INVALID);RWMode(rq_wizard,"auto");}
 object rq_cleric=GetObjectByTag("rq_cleric");
 if(GetIsObjectValid(rq_cleric) && !GetIsObjectValid(RWFind("rq_cleric"))){SetLocalString(rq_cleric,"rw_source","world");RWBind(rq_cleric,"rq_cleric",OBJECT_INVALID);RWMode(rq_cleric,"auto");}
 object rq_holt=GetObjectByTag("rq_holt");
 if(GetIsObjectValid(rq_holt) && !GetIsObjectValid(RWFind("rq_holt"))){SetLocalString(rq_holt,"rw_source","world");RWBind(rq_holt,"rq_holt",OBJECT_INVALID);RWMode(rq_holt,"auto");}
WriteTimestampedLogEntry("ROLEWEAVER QUEST: investigation initialized with four witnesses and noticeboard.");
}
