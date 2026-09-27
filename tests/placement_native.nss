// Disposable-world regression for restore position drift.
#include "rw_creature"
void Cycle(int n,location where,location original)
{
    json build=JsonParse("{\"appearance\":6,\"race\":6,\"gender\":1,\"npc_class\":4,\"level\":1}");
    object npc=RWCreateCreature(build,where);
    if(!GetIsObjectValid(npc)){WriteTimestampedLogEntry("RW_PLACE_TEST create FAIL");return;}
    location actual=GetLocation(npc);vector p=GetPosition(npc);
    float delta=GetDistanceBetweenLocations(where,actual);float total=GetDistanceBetweenLocations(original,actual);
    WriteTimestampedLogEntry("RW_PLACE_TEST cycle="+IntToString(n)+" step="+FloatToString(delta)+" total="+FloatToString(total)+" x="+FloatToString(p.x)+" y="+FloatToString(p.y)+(total<0.01?" PASS":" FAIL"));
    DestroyObject(npc);
    if(n<5)DelayCommand(1.0,Cycle(n+1,actual,original));
    else WriteTimestampedLogEntry("RW_PLACE_TEST FINISHED");
}
void Begin()
{object area=GetObjectByTag("throne_room");if(!GetIsObjectValid(area))area=GetFirstArea();location l=Location(area,Vector(30.0,25.0,0.0),45.0);Cycle(1,l,l);}
void main(){DelayCommand(2.0,Begin());}
