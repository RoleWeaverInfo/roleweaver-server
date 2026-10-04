// Called only after Role Weaver has successfully broadcast a public line.
#include "rw_hearing"
void main()
{
    RWCPHearPublic(GetLocalObject(GetModule(),"rw_hear_speaker"),GetLocalString(GetModule(),"rw_hear_text"));
}
