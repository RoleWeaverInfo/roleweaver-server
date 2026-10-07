// In-game player controls. Explicit dimensions avoid narrow default NUI columns.
#include "rw_cp_visit"

json RWCPMenuButton(string label,string id,float width=300.0,string enabled="")
{
    json button=NuiWidth(NuiHeight(NuiId(NuiButton(JsonString(label)),id),32.0),width);
    if(enabled!="")button=NuiEnabled(button,NuiBind(enabled));
    return button;
}
int RWCPMenuValid(object owner,int token)
{
    return GetIsPC(owner) && !GetIsDM(owner) && !GetIsDMPossessed(owner) && !GetIsPossessedFamiliar(owner)
        && token>0 && token==GetLocalInt(owner,"rw_cp_menu_token")
        && NuiGetWindowId(owner,token)=="rwcompanionsettings"
        && GetLocalString(owner,"rw_cp_menu_session")==GetLocalString(GetModule(),"rw_session")
        && GetLocalInt(owner,"rw_cp_menu_type")==GetFamiliarCreatureType(owner)
        && GetLocalObject(owner,"rw_cp_menu_familiar")==RWCPFind(owner)
        && GetLocalInt(owner,"rw_cp_menu_until")>GetLocalInt(GetModule(),"rw_tick");
}
string RWCPOnOff(int value){return value?"ON":"OFF";}
void RWCPMenuRefresh(object owner,string notice="")
{
    int token=GetLocalInt(owner,"rw_cp_menu_token");if(!RWCPMenuValid(owner,token))return;
    object familiar=RWCPFind(owner);json p=RWCPPreferences(owner);
    int enabled=GetLocalInt(owner,"rw_cp_on") && GetLocalString(owner,"rw_cp_login_session")==GetLocalString(GetModule(),"rw_session");
    int nearby=RWCPReady(owner,familiar) && GetDistanceBetween(owner,familiar)<=RWHearingRange() && LineOfSightObject(owner,familiar);
    string status="";
    if(!GetLocalInt(GetModule(),"rw_cp_enabled"))status="Companion AI is unavailable or disabled by the server.";
    else if(!RWCPPreferencesReady(owner))status="Loading or saving preferences. Companion commands pause until the service confirms.";
    else if(!GetIsObjectValid(familiar))status="Summon your familiar to use AI conversation and commands.";
    else if(!enabled)status="AI is OFF. Enable it for this login when you are ready.";
    else if(!RWCPReady(owner,familiar))status="AI is ON, but paused by combat, possession, conversation or separation.";
    else if(!nearby)status="AI is ON. Approach your familiar within hearing range and line of sight to give commands.";
    else status=GetStringLeft(GetName(familiar),60)+": ready. Replies appear in nearby Talk chat.";
    if(GetLocalString(familiar,"rw_cpv_id")!="")status=GetLocalString(familiar,"rw_cpv_status");
    NuiSetBind(owner,token,"status",JsonString(status));NuiSetBind(owner,token,"notice",JsonString(notice));
    NuiSetBind(owner,token,"can_preferences",JsonBool(RWCPPreferencesReady(owner)));
    NuiSetBind(owner,token,"toggle_label",JsonString(enabled?"Disable AI for this login":"Enable AI for this login"));
    NuiSetBind(owner,token,"can_toggle",JsonBool(enabled || (GetLocalInt(GetModule(),"rw_cp_enabled") && GetIsObjectValid(familiar))));
    NuiSetBind(owner,token,"can_move",JsonBool(nearby && RWI(p,"movement")));
    NuiSetBind(owner,token,"can_inventory",JsonBool(nearby && RWCPIEnabled() && RWI(p,"inventory")));
    json lengths=JsonParse("[\"Brief\",\"Natural\",\"Detailed\"]");json tones=JsonParse("[\"Character default\",\"Warm\",\"Playful\",\"Reserved\",\"Serious\"]");
    NuiSetBind(owner,token,"reply_label",JsonString("Reply length: "+JsonGetString(JsonArrayGet(lengths,RWI(p,"reply")))));
    NuiSetBind(owner,token,"tone_label",JsonString("Tone: "+JsonGetString(JsonArrayGet(tones,RWI(p,"tone")))));
    NuiSetBind(owner,token,"followups_label",JsonString("Follow-up conversation: "+RWCPOnOff(RWI(p,"followups"))));
    NuiSetBind(owner,token,"movement_label",JsonString("AI movement: "+RWCPOnOff(RWI(p,"movement"))));
    NuiSetBind(owner,token,"inventory_label",JsonString("Satchel exchanges: "+RWCPOnOff(RWI(p,"inventory"))));
    NuiSetBind(owner,token,"collect_label",JsonString("Collect and fetch: "+RWCPOnOff(RWI(p,"collect"))));
    NuiSetBind(owner,token,"deliver_label",JsonString("Give or barter with others: "+RWCPOnOff(RWI(p,"deliver"))));
    NuiSetBind(owner,token,"listening_label",JsonString("Local listening: "+(GetLocalInt(GetModule(),"rw_cp_listening")?RWCPOnOff(RWI(p,"listening")):"unavailable")));
}
json RWCPMenuSetting(string key)
{return NuiEnabled(NuiWidth(NuiHeight(NuiId(NuiButton(NuiBind(key+"_label")),key),32.0),300.0),NuiBind("can_preferences"));}
int RWCPMenu(object owner)
{
    if(!GetIsPC(owner) || GetIsDM(owner) || GetIsDMPossessed(owner) || GetIsPossessedFamiliar(owner))return FALSE;
    RWCPInitialize(owner);
    int old=NuiFindWindow(owner,"rwcompanionsettings");DeleteLocalInt(owner,"rw_cp_menu_token");if(old)NuiDestroy(owner,old);
    json col=JsonArray(),row=JsonArray();
    col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiText(NuiBind("status"),FALSE,0),48.0),612.0));
    row=JsonArrayInsert(row,NuiEnabled(NuiWidth(NuiHeight(NuiId(NuiButton(NuiBind("toggle_label")),"toggle"),32.0),300.0),NuiBind("can_toggle")));
    row=JsonArrayInsert(row,RWCPMenuButton("Refresh status","refresh"));col=JsonArrayInsert(col,NuiRow(row));
    row=JsonArray();row=JsonArrayInsert(row,RWCPMenuSetting("reply"));row=JsonArrayInsert(row,RWCPMenuSetting("tone"));col=JsonArrayInsert(col,NuiRow(row));
    row=JsonArray();row=JsonArrayInsert(row,RWCPMenuSetting("followups"));row=JsonArrayInsert(row,RWCPMenuSetting("movement"));col=JsonArrayInsert(col,NuiRow(row));
    row=JsonArray();row=JsonArrayInsert(row,RWCPMenuSetting("inventory"));row=JsonArrayInsert(row,RWCPMenuSetting("collect"));col=JsonArrayInsert(col,NuiRow(row));
    row=JsonArray();row=JsonArrayInsert(row,RWCPMenuSetting("deliver"));row=JsonArrayInsert(row,RWCPMenuSetting("listening"));col=JsonArrayInsert(col,NuiRow(row));
    row=JsonArray();row=JsonArrayInsert(row,RWCPMenuButton("Follow me","follow",300.0,"can_move"));row=JsonArrayInsert(row,RWCPMenuButton("Stand ground","stay",300.0,"can_move"));col=JsonArrayInsert(col,NuiRow(row));
    row=JsonArray();row=JsonArrayInsert(row,RWCPMenuButton("Open inventory","inventory_open",300.0,"can_inventory"));row=JsonArrayInsert(row,RWCPMenuButton("Recover satchel items","recover"));col=JsonArrayInsert(col,NuiRow(row));
    row=JsonArray();row=JsonArrayInsert(row,RWCPMenuButton("End conversation","end"));row=JsonArrayInsert(row,RWCPMenuButton("Cancel current errand","cancel"));col=JsonArrayInsert(col,NuiRow(row));
    col=JsonArrayInsert(col,RWCPMenuButton("Reset these preferences","reset",300.0,"can_preferences"));
    col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiText(JsonString("Click a preference to change it; changes save immediately for this character and familiar type. Follow-ups let you talk without repeating its name. Item errands need satchel exchanges and movement enabled. If movement is off, approach your familiar to exchange items. Recovery remains available. Server restrictions and normal familiar controls still apply. Tone changes delivery, not the character's history. AI starts enabled each login when the server allows it; you can disable it above."),FALSE,0),120.0),612.0));
    col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiText(NuiBind("notice"),FALSE,0),44.0),612.0));
    col=JsonArrayInsert(col,NuiWidth(NuiHeight(NuiText(JsonString("Local listening remembers up to 8 nearby public lines for 2 minutes, for your next conversation. No private chat, automatic replies or extra AI requests. Turn it off to clear the short history."),FALSE,0),62.0),612.0));
    int token=NuiCreate(owner,NuiWindow(NuiCol(col),JsonString("Role Weaver - Companion settings"),NuiRect(-1.0,-1.0,660.0,700.0),JSON_FALSE,JSON_FALSE,JSON_TRUE,JSON_FALSE,JSON_TRUE),"rwcompanionsettings","rw_cp_menu_evt");
    if(!token)return FALSE;
    SetLocalInt(owner,"rw_cp_menu_token",token);SetLocalString(owner,"rw_cp_menu_session",GetLocalString(GetModule(),"rw_session"));
    SetLocalInt(owner,"rw_cp_menu_type",GetFamiliarCreatureType(owner));SetLocalObject(owner,"rw_cp_menu_familiar",RWCPFind(owner));
    SetLocalInt(owner,"rw_cp_menu_until",GetLocalInt(GetModule(),"rw_tick")+600);RWCPMenuRefresh(owner);return TRUE;
}
