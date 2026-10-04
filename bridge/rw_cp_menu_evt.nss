// All actions are resolved from the event player, never a supplied owner/target.
#include "rw_companion"
void main()
{
    object owner=NuiGetEventPlayer();int token=NuiGetEventWindow();
    if(token!=GetLocalInt(owner,"rw_cp_menu_token"))return;
    if(NuiGetEventType()=="close"){DeleteLocalInt(owner,"rw_cp_menu_token");return;}
    if(NuiGetEventType()!="click")return;
    if(!RWCPMenuValid(owner,token))
    {DeleteLocalInt(owner,"rw_cp_menu_token");NuiDestroy(owner,token);SendMessageToPC(owner,"Your companion changed or this menu expired. Reopen /rw companion settings.");return;}
    string id=NuiGetEventElement(),notice="";json p=RWCPPreferences(owner);int preference=FALSE;
    if(id=="reply"){p=JsonObjectSet(p,id,JsonInt((RWI(p,id)+1)%3));preference=TRUE;}
    else if(id=="tone"){p=JsonObjectSet(p,id,JsonInt((RWI(p,id)+1)%5));preference=TRUE;}
    else if(id=="followups" || id=="movement" || id=="inventory" || id=="collect" || id=="deliver" || id=="listening")
    {p=JsonObjectSet(p,id,JsonInt(!RWI(p,id)));preference=TRUE;}
    else if(id=="reset"){p=RWCPDefaultPrefs();preference=TRUE;}
    if(preference)
    {
        if(!RWCPPreferencesReady(owner)){RWCPMenuRefresh(owner,"Wait for the service to confirm your preferences.");return;}
        if(id=="listening" && !GetLocalInt(GetModule(),"rw_cp_listening")){RWCPMenuRefresh(owner,"Local listening is unavailable or disabled by the server.");return;}
        RWCPVCancel(RWCPFind(owner),"Preferences changed; visit cancelled.",TRUE);
        RWCPICancel(RWCPFind(owner),"Preferences changed; previous errand cancelled.",TRUE);
        if(!RWCPStorePrefs(owner,p)){RWCPMenuRefresh(owner,"Preferences could not be saved. Existing limits still apply; ask the DM to check the character's saved settings.");return;}
        RWCPHearClear(RWCPFind(owner));
        RWCPEndTalk(owner);RWCPInvalidate(owner);RWCPTick(owner);
        notice="Saving preferences. Pending replies and errands cancelled. Wait for confirmation before chatting.";
    }
    else if(id=="toggle")
    {
        int enabled=GetLocalInt(owner,"rw_cp_on") && GetLocalString(owner,"rw_cp_login_session")==GetLocalString(GetModule(),"rw_session");
        RWCPChat(owner,enabled?"/rw companion off":"/rw companion on");
    }
    else if(id=="follow")RWCPChat(owner,"/rw companion follow me");
    else if(id=="stay")RWCPChat(owner,"/rw companion stay here");
    else if(id=="inventory_open")RWCPChat(owner,"/rw companion inventory");
    else if(id=="recover")RWCPChat(owner,"/rw companion recover");
    else if(id=="end"){RWCPEndTalk(owner);RWCPInvalidate(owner);notice="Conversation ended. Address your familiar again when ready.";}
    else if(id=="cancel")RWCPChat(owner,"/rw companion cancel");
    else if(id=="refresh")RWCPRequestPrefs(owner);
    else return;
    RWCPMenuRefresh(owner,notice);
}
