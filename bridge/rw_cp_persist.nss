// Batch companion inventory saves. State belongs to the module, never to the
// exported character: loading a character cannot restore an old pending timer.
// Native world autosaves, merchant payments and other systems remain separate.
string RWCPSKey(object player) {return "rw_cps_"+ObjectToString(player);}
int RWCPSInterval()
{
    int seconds=GetLocalInt(GetModule(),"rw_cp_save_seconds");
    if(seconds<=0)return 600;
    if(seconds<30)return 30;
    if(seconds>3600)return 3600;
    return seconds;
}
void RWCPSClear(object player)
{
    object m=GetModule();string key=RWCPSKey(player);
    DeleteLocalInt(m,key+"dirty");DeleteLocalInt(m,key+"pending");
    DeleteLocalString(m,key+"session");
}
void RWCPSFlush(object player)
{
    object m=GetModule();string key=RWCPSKey(player);
    int dirty=GetLocalInt(m,key+"dirty")
        && GetLocalString(m,key+"session")==GetLocalString(m,"rw_session");
    // Invalidate the timer before exporting. Export callbacks must not enqueue
    // another export of the same inventory and start a save loop.
    RWCPSClear(player);
    if(!dirty || !GetIsPC(player) || GetLocalInt(m,"rw_cp_save_disabled") || GetLocalInt(m,key+"saving"))return;
    SetLocalInt(m,key+"saving",TRUE);
    ExportSingleCharacter(player);
    DeleteLocalInt(m,key+"saving");
}
void RWCPSScheduled(object player,int token,string session)
{
    object m=GetModule();string key=RWCPSKey(player);
    if(GetLocalInt(m,key+"pending")!=token || session!=GetLocalString(m,"rw_session"))return;
    RWCPSFlush(player);
}
void RWCPSRequest(object player)
{
    object m=GetModule();string key=RWCPSKey(player),session=GetLocalString(m,"rw_session");
    if(!GetIsPC(player) || GetLocalInt(m,"rw_cp_save_disabled") || GetLocalInt(m,key+"saving"))return;
    if(GetLocalString(m,key+"session")!=session)RWCPSClear(player);
    SetLocalString(m,key+"session",session);SetLocalInt(m,key+"dirty",TRUE);
    if(GetLocalInt(m,key+"pending"))return;
    int token=GetLocalInt(m,"rw_cps_token")+1;
    if(token<=0)token=1;
    SetLocalInt(m,"rw_cps_token",token);SetLocalInt(m,key+"pending",token);
    // A fixed window, not a debounce: continual item moves cannot postpone a
    // save forever. Module ownership keeps the timer outside creature actions.
    AssignCommand(m,DelayCommand(IntToFloat(RWCPSInterval()),RWCPSScheduled(player,token,session)));
}
void RWCPISave(object owner,object recipient=OBJECT_INVALID)
{
    RWCPSRequest(owner);
    if(recipient!=owner)RWCPSRequest(recipient);
}
