#include "rq_inc"
void main()
{
 object pc=GetPCChatSpeaker();string line=GetPCChatMessage();
 if(GetIsPC(pc)&&!GetIsDM(pc)&&!GetIsDMPossessed(pc)&&GetPCChatVolume()==TALKVOLUME_TALK&&GetStringLowerCase(line)=="/case")
 {RQNotes(pc);SetPCChatMessage("");return;}
 // Every spoken story exchange reaches Role Weaver and its normal safeguards.
 ExecuteScript("rw_worldchat",GetModule());
}
