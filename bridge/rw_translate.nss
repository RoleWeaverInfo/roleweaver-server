// Private reading windows and name overrides: never replace shared object text.
#include "rw_inc"
#include "nw_inc_nui"
#include "nwnx_player"

string RWTrNameMode(object o)
{
 // Player identity stays exactly as written, including in Examine windows.
 if(GetIsPC(o))return "preserve";
 int mode=GetLocalInt(o,"rw_tr_name_mode");
 if(mode==1)return "preserve";
 if(mode==2)return "translate";
 return "auto";
}
int RWTrEligible(object o)
{
 int type=GetObjectType(o);
 // Include the public Examine description of ordinary NPCs, AI NPCs and PCs.
 // AI personality, private lore and memory never enter this path.
 if(!GetIsObjectValid(o) || GetLocalInt(o,"rw_no_translate"))return FALSE;
 if(type==OBJECT_TYPE_CREATURE)return !GetIsDM(o) && !GetIsDMPossessed(o);
 if(type!=OBJECT_TYPE_ITEM && type!=OBJECT_TYPE_PLACEABLE && type!=OBJECT_TYPE_DOOR)return FALSE;
 if(type==OBJECT_TYPE_ITEM && !GetIdentified(o))return FALSE;
 return TRUE;
}
void RWTrClose(object pc)
{int token=NuiFindWindow(pc,"rwtranslation");if(token)NuiDestroy(pc,token);}
// These NWNX overrides affect only the observer. Never override a player's name.
void RWTrApplyName(object pc,object o,string value)
{
 // Clearing our existing override remains allowed if the DM has since taken
 // possession; applying a new translated player/possessed name is forbidden.
 if(!GetIsPC(pc) || !GetIsObjectValid(o) || ((GetIsPC(o) || GetIsDMPossessed(o)) && value!="")
   || !NWNX_Core_PluginExists("NWNX_Player"))return;
 if(GetObjectType(o)==OBJECT_TYPE_PLACEABLE)NWNX_Player_SetPlaceableNameOverride(pc,o,value);
 else if(GetObjectType(o)==OBJECT_TYPE_CREATURE)NWNX_Player_SetCreatureNameOverride(pc,o,value);
}
void RWTrClearNames(object pc)
{
 int i,count=GetLocalInt(pc,"rw_tr_name_count");
 for(i=0;i<count;i++)
 {
  string key="rw_tr_name_"+IntToString(i);RWTrApplyName(pc,GetLocalObject(pc,key),"");
  DeleteLocalObject(pc,key);DeleteLocalString(pc,key);DeleteLocalString(pc,key+"_mode");DeleteLocalString(pc,key+"_display");
 }
 DeleteLocalInt(pc,"rw_tr_name_count");DeleteLocalInt(pc,"rw_tr_name_cursor");
 SetLocalInt(pc,"rw_tr_names_seq",GetLocalInt(pc,"rw_tr_names_seq")+1);
}
// Recognize only this observer's current translated label as an addressing alias.
string RWTrNameAlias(object pc,object npc)
{
 if(!GetLocalInt(pc,"rw_tr_enabled") || GetIsPC(npc) || GetLocalInt(npc,"rw_no_translate") || RWTrNameMode(npc)=="preserve")return "";
 int i,count=GetLocalInt(pc,"rw_tr_name_count");
 for(i=0;i<count;i++)
 {
  string key="rw_tr_name_"+IntToString(i);
  if(GetLocalObject(pc,key)==npc && GetLocalString(pc,key)==GetName(npc)
    && GetLocalString(pc,key+"_mode")==RWTrNameMode(npc))return GetLocalString(pc,key+"_display");
 }
 return "";
}
// Optional DM exclusion, including public character descriptions.
void RWTrSetExcluded(object o,int excluded)
{
 if(excluded)SetLocalInt(o,"rw_no_translate",TRUE);
 else DeleteLocalInt(o,"rw_no_translate");
 if(!excluded)return;
 object pc=GetFirstPC();
 while(GetIsObjectValid(pc))
 {
  RWTrApplyName(pc,o,"");
  if(GetLocalObject(pc,"rw_tr_object")==o)
  {
   RWTrClose(pc);
   DeleteLocalObject(pc,"rw_tr_object");
   SetLocalInt(pc,"rw_tr_seq",GetLocalInt(pc,"rw_tr_seq")+1);
  }
  pc=GetNextPC();
 }
}
json RWTrEvent(object pc,string kind)
{
 string token=GetLocalString(pc,"rw_tr_token");
 if(token==""){token=IntToString(Random(2000000000))+"_"+ObjectToString(pc);SetLocalString(pc,"rw_tr_token",token);}
 string sequenceKey=kind=="translation_names"?"rw_tr_names_seq":(kind=="translation_dialogue"?"rw_tr_nodes_seq":"rw_tr_seq");
 int seq=GetLocalInt(pc,sequenceKey)+1;SetLocalInt(pc,sequenceKey,seq);
 json e=RWBase(kind,OBJECT_INVALID);
 e=JsonObjectSet(e,"player",JsonString(ObjectToString(pc)));
 e=JsonObjectSet(e,"identity",JsonString(GetPCPublicCDKey(pc)));
 e=JsonObjectSet(e,"token",JsonString(token));e=JsonObjectSet(e,"seq",JsonInt(seq));return e;
}
void RWTrLoad(object pc)
{
 if(!GetIsPC(pc) || GetIsDMPossessed(pc))return;
 int tick=GetLocalInt(GetModule(),"rw_tick");
 if(GetLocalInt(pc,"rw_tr_next")>tick || GetLocalInt(pc,"rw_tr_dialog_pending"))return;
 SetLocalInt(pc,"rw_tr_next",tick+15);RWEmit(RWTrEvent(pc,"translation_player"));
}
void RWTrStatus(object pc)
{
 int token=NuiFindWindow(pc,"rwlanguage");if(!token)return;
 string s="Loading saved preference...";
 if(GetLocalInt(pc,"rw_tr_loaded"))
 {
  s="Translation "+(GetLocalInt(pc,"rw_tr_preference")?"ON":"OFF")+" | language: "+GetLocalString(pc,"rw_tr_language");
  if(!GetLocalInt(pc,"rw_tr_service"))s+=" | service disabled";
 }
 NuiSetBind(pc,token,"status",JsonString(s));
}
// NUI does not stretch direct column children to the window width. Give each
// control its content width explicitly, leaving room for borders and padding.
json RWTrSized(json control,float width,float height)
{
 return NuiWidth(NuiHeight(control,height),width);
}
void RWTrMenu(object pc)
{
 int old=NuiFindWindow(pc,"rwlanguage");if(old)NuiDestroy(pc,old);
 json col=JsonArray();
 col=JsonArrayInsert(col,RWTrSized(NuiLabel(NuiBind("status"),JsonInt(0),JsonInt(1)),440.0,35.0));
 col=JsonArrayInsert(col,RWTrSized(NuiId(NuiButton(JsonString("Turn translation ON / OFF")),"toggle"),440.0,35.0));
 string codes="en,fr,es,de,it,pt";
 json names=JsonParse("[\"English\",\"French / Francais\",\"Spanish / Espanol\",\"German / Deutsch\",\"Italian / Italiano\",\"Portuguese / Portugues\"]");
 int i;for(i=0;i<6;i++)col=JsonArrayInsert(col,RWTrSized(NuiId(NuiButton(JsonArrayGet(names,i)),"lang_"+GetSubString(codes,i*3,2)),440.0,30.0));
 col=JsonArrayInsert(col,RWTrSized(NuiText(JsonString("Choose a language, then turn translation on. Your preference is saved between logins. Only languages enabled by the server can be selected. New or changed text appears in the original language first. Close and reopen Examine later to see a cached translation in a private reading window. Chat and logs are never translated."),FALSE,2),440.0,145.0));
 NuiCreate(pc,NuiWindow(NuiCol(col),JsonString("Language and translation"),NuiRect(-1.0,-1.0,480.0,520.0),JSON_FALSE,JSON_FALSE,JSON_TRUE,JSON_FALSE,JSON_TRUE),"rwlanguage","rw_tr_nui");
 RWTrStatus(pc);
 if(!GetLocalInt(pc,"rw_tr_loaded")){DeleteLocalInt(pc,"rw_tr_next");RWTrLoad(pc);}
}
void RWTrExamine(object pc,object o)
{
 RWTrClose(pc);
 // Any new examination cancels an earlier response, including excluded objects.
 SetLocalInt(pc,"rw_tr_seq",GetLocalInt(pc,"rw_tr_seq")+1);
 DeleteLocalObject(pc,"rw_tr_object");
 if(!GetIsPC(pc) || GetIsDMPossessed(pc) || !RWTrEligible(o) || !GetLocalInt(pc,"rw_tr_enabled"))return;
 string name=GetName(o),description=GetDescription(o);
 int playerDescription=GetObjectType(o)==OBJECT_TYPE_CREATURE && GetIsPC(o);
 if(GetStringLength(name)>2000 || GetStringLength(description)>(GetObjectType(o)==OBJECT_TYPE_CREATURE?8000:2000))return;
 // GetDescription reads the publicly examined text, never account metadata,
 // private profiles, chat or logs. No per-character opt-in is required.
 json e=RWTrEvent(pc,"translation_examine");
 e=JsonObjectSet(e,"approved",JsonInt(1));e=JsonObjectSet(e,"object",JsonString(ObjectToString(o)));
 e=JsonObjectSet(e,"object_type",JsonInt(GetObjectType(o)));
 e=JsonObjectSet(e,"player_character",JsonInt(playerDescription));
 e=JsonObjectSet(e,"resref",JsonString(playerDescription?"":GetResRef(o)));
 e=JsonObjectSet(e,"name_mode",JsonString(RWTrNameMode(o)));
 e=JsonObjectSet(e,"name",JsonString(name));e=JsonObjectSet(e,"description",JsonString(description));
 SetLocalObject(pc,"rw_tr_object",o);RWEmit(e);
}
void RWTrReply(json cmd)
{
 object pc=StringToObject(RWS(cmd,"player"));
 if(!GetIsPC(pc) || GetIsDMPossessed(pc) || RWS(cmd,"world")!=RWWorld()
  || RWS(cmd,"session")!=GetLocalString(GetModule(),"rw_session") || RWS(cmd,"token")!=GetLocalString(pc,"rw_tr_token")
  || RWI(cmd,"seq")!=GetLocalInt(pc,"rw_tr_seq") || RWI(cmd,"expires")<GetLocalInt(GetModule(),"rw_tick"))return;
 SetLocalInt(pc,"rw_tr_enabled",RWI(cmd,"enabled"));SetLocalInt(pc,"rw_tr_preference",RWI(cmd,"preference_enabled"));
 SetLocalInt(pc,"rw_tr_service",RWI(cmd,"service_enabled"));SetLocalInt(pc,"rw_tr_loaded",TRUE);
 SetLocalString(pc,"rw_tr_language",RWS(cmd,"language"));SetLocalString(pc,"rw_tr_languages",JsonDump(JsonObjectGet(cmd,"languages")));RWTrStatus(pc);
 if(!RWI(cmd,"enabled")){RWTrClose(pc);RWTrClearNames(pc);return;}
 if(RWS(cmd,"object")=="")return;
 object o=StringToObject(RWS(cmd,"object"));
 if(!RWTrEligible(o) || o!=GetLocalObject(pc,"rw_tr_object") || GetName(o)!=RWS(cmd,"source_name") || GetDescription(o)!=RWS(cmd,"source_description") || RWTrNameMode(o)!=RWS(cmd,"name_mode"))return;
 if(RWS(cmd,"description")=="" && (GetIsPC(o) || RWS(cmd,"name")==""))return;
 // Enforce name preservation again at display time, even if a companion sends
 // a translated name. The original/translated toggle shares this same header.
 string displayName=GetIsPC(o) || RWS(cmd,"name")==""?GetName(o):RWS(cmd,"name");
 string displayDescription=RWS(cmd,"description")==""?GetDescription(o):RWS(cmd,"description");
 json display=JsonString(displayName+"\n\n"+displayDescription);
 RWTrClose(pc);
 json col=JsonArray();col=JsonArrayInsert(col,RWTrSized(NuiText(NuiBind("body"),TRUE,2),580.0,360.0));
 col=JsonArrayInsert(col,RWTrSized(NuiId(NuiButton(NuiBind("toggle_label")),"original"),580.0,32.0));
 int token=NuiCreate(pc,NuiWindow(NuiCol(col),JsonString(GetObjectType(o)==OBJECT_TYPE_CREATURE?"Character description translation":"World text translation"),NuiRect(-1.0,-1.0,620.0,450.0),JSON_FALSE,JSON_FALSE,JSON_TRUE,JSON_FALSE,JSON_TRUE),"rwtranslation","rw_tr_nui");
 NuiSetBind(pc,token,"body",display);
 NuiSetBind(pc,token,"translated",display);
 NuiSetBind(pc,token,"showing_original",JsonInt(0));
 NuiSetBind(pc,token,"toggle_label",JsonString("Show original text"));
 NuiSetBind(pc,token,"original",JsonString(GetName(o)+"\n\n"+GetDescription(o)));
}
