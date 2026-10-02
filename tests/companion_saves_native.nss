// Run with run_companion_saves_native.py in a disposable world. The runner
// substitutes PC eligibility and the actual export with tagged fixture counters.
// The production scheduler, queue, module state and delays execute unchanged.
#include "rw_cp_persist"
void Check(int ok,string label)
{WriteTimestampedLogEntry("RW_SAVE_TEST "+(ok?"PASS ":"FAIL ")+label);}
int Saves(object player) {return GetLocalInt(player,"fixture_exports");}
object Player(string tag)
{
    object player=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",Location(GetFirstArea(),Vector(10.0,10.0,0.0),0.0));
    SetLocalInt(player,"fixture_player",TRUE);SetLocalObject(GetModule(),tag,player);return player;
}
void MoreChanges(object player)
{
    int token=GetLocalInt(GetModule(),RWCPSKey(player)+"pending");
    RWCPISave(player);
    Check(GetLocalInt(GetModule(),RWCPSKey(player)+"pending")==token,"later changes retain the original deadline");
    Check(Saves(player)==0,"no early export before the configured interval");
}
void Finished()
{
    object m=GetModule(),a=GetLocalObject(m,"a"),b=GetLocalObject(m,"b"),logout=GetLocalObject(m,"logout");
    Check(Saves(a)==1 && Saves(b)==1,"one timed export per changed player despite repeated requests");
    Check(!GetLocalInt(m,RWCPSKey(a)+"pending") && !GetLocalInt(m,RWCPSKey(a)+"dirty"),"export callbacks do not requeue saves");
    Check(Saves(logout)==1,"logout invalidates its previously scheduled timer");
    RWCPSFlush(a);RWCPSFlush(b);
    Check(Saves(a)==1 && Saves(b)==1,"clean logout adds no export");
    RWCPISave(a);int token=GetLocalInt(m,RWCPSKey(a)+"pending");
    RWCPSFlush(a);RWCPSScheduled(a,token,GetLocalString(m,"rw_session"));
    Check(Saves(a)==2,"later dirty changes flush once and invalidate the timer");
    WriteTimestampedLogEntry("RW_SAVE_TEST FINISHED");
}
void main()
{
    // The export stand-in invokes this script to simulate an inventory callback
    // during export. It must not produce another queued save.
    if(OBJECT_SELF!=GetModule()){RWCPSRequest(OBJECT_SELF);return;}
    object m=GetModule();SetLocalString(m,"rw_session","save-test");
    Check(RWCPSInterval()==600,"default interval is ten minutes");
    SetLocalInt(m,"rw_cp_save_seconds",1);Check(RWCPSInterval()==30,"minimum custom interval is thirty seconds");
    SetLocalInt(m,"rw_cp_save_seconds",7200);Check(RWCPSInterval()==3600,"maximum custom interval is one hour");
    // Verify the production default above, then use a short supported interval
    // for the timed regression without waiting ten minutes on each test run.
    SetLocalInt(m,"rw_cp_save_seconds",30);
    object a=Player("a"),b=Player("b"),logout=Player("logout"),disabled=Player("disabled");
    RWCPSFlush(a);Check(Saves(a)==0,"unchanged inventory does not export");
    RWCPISave(OBJECT_INVALID);Check(!GetLocalInt(m,RWCPSKey(OBJECT_INVALID)+"pending"),"invalid players are ignored");
    RWCPISave(a,b);int token=GetLocalInt(m,RWCPSKey(a)+"pending"),i;
    for(i=0;i<100;i++)RWCPISave(a,a);
    Check(Saves(a)==0 && GetLocalInt(m,RWCPSKey(a)+"pending")==token,"native and explicit requests coalesce without immediate exports");
    RWCPSScheduled(a,token+99,"save-test");RWCPSScheduled(a,token,"old-session");
    Check(Saves(a)==0 && GetLocalInt(m,RWCPSKey(a)+"pending")==token,"stale callbacks cannot flush an active queue");
    RWCPISave(logout);token=GetLocalInt(m,RWCPSKey(logout)+"pending");RWCPSFlush(logout);
    Check(Saves(logout)==1 && !GetLocalInt(m,RWCPSKey(logout)+"pending"),"dirty logout flushes without waiting");
    // A new session must not be flushed by an old callback for the same object.
    RWCPISave(logout);int newToken=GetLocalInt(m,RWCPSKey(logout)+"pending");
    RWCPSScheduled(logout,token,"save-test");
    Check(Saves(logout)==1 && GetLocalInt(m,RWCPSKey(logout)+"pending")==newToken,"old timer cannot flush a newly queued request");
    RWCPSClear(logout);
    RWCPISave(disabled);SetLocalInt(m,"rw_cp_save_disabled",TRUE);RWCPSFlush(disabled);RWCPISave(disabled);
    Check(Saves(disabled)==0 && !GetLocalInt(m,RWCPSKey(disabled)+"pending"),"custom world save policy disables queued and new exports");
    DeleteLocalInt(m,"rw_cp_save_disabled");
    DelayCommand(10.0,MoreChanges(a));DelayCommand(35.0,Finished());
}
