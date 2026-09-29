// Ordinary DLG translation. Included by generated condition wrappers and rw_tick.
// No branch selection, quest action or AI instruction is accepted from a provider.
#include "rw_translate"
#include "nwnx_dialog"
#include "nwnx_util"
#include "rw_tr_native"

string RWTrNodeKey(int token) { return "rw_td_"+IntToString(token); }

// Compatibility fallback when the optional recipient-delivery plugin is absent.
// The new plugin never uses this area-wide restriction or shared token edits.
int RWTrNodePrivateView(object pc)
{
 object other=GetFirstPC();
 while(GetIsObjectValid(other))
 {
  if(other!=pc && GetArea(other)==GetArea(pc))return FALSE;
  other=GetNextPC();
 }
 return TRUE;
}

// Restore the authored node before evaluating its original condition again.
// The DLG on disk is unchanged; only this active conversation instance is edited.
void RWTrNodeRestore(int token)
{
 if(!NWNX_Core_PluginExists("NWNX_Dialog"))return;
 string key=RWTrNodeKey(token), marker="<CUSTOM"+IntToString(token)+">";
 int i,gender;json langs=JsonParse("[0,1,2,3,4,5,128,129,130,131]");
 for(i=0;i<JsonGetLength(langs);i++)for(gender=0;gender<2;gender++)
 {
  int language=JsonGetInt(JsonArrayGet(langs,i));string slot=key+"_o"+IntToString(language)+"_"+IntToString(gender);
  if(GetLocalInt(OBJECT_SELF,slot) && NWNX_Dialog_GetCurrentNodeText(language,gender)==marker)
   NWNX_Dialog_SetCurrentNodeText(GetLocalString(OBJECT_SELF,slot),language,gender);
 }
}

// Bounded per-player working set; the durable shared cache belongs to the companion.
void RWTrNodeRemember(object pc,string key,string source)
{
 if(!GetLocalInt(pc,key+"_tracked"))
 {
  int cursor=GetLocalInt(pc,"rw_td_cursor");string ring="rw_td_ring_"+IntToString(cursor);
  string old=GetLocalString(pc,ring);
  if(old!="")
  {
   DeleteLocalString(pc,old);DeleteLocalString(pc,old+"_value");DeleteLocalString(pc,old+"_language");
   DeleteLocalString(pc,old+"_request");DeleteLocalInt(pc,old+"_tracked");DeleteLocalInt(pc,old+"_time");DeleteLocalInt(pc,old+"_seq");
  }
  SetLocalString(pc,ring,key);SetLocalInt(pc,"rw_td_cursor",(cursor+1)%64);SetLocalInt(pc,key+"_tracked",TRUE);
 }
 if(GetLocalString(pc,key)!=source)
 {
  SetLocalString(pc,key,source);DeleteLocalString(pc,key+"_value");DeleteLocalString(pc,key+"_language");
 }
}

void RWTrNodeRequest(object pc,object speaker,string resource,string kind,int index,int token,string source)
{
 string key=RWTrNodeKey(token);
 json e=RWTrEvent(pc,"translation_dialogue");e=JsonObjectSet(e,"on_demand",JsonInt(1));
 e=JsonObjectSet(e,"dialogue",JsonString(resource));e=JsonObjectSet(e,"speaker",JsonString(ObjectToString(speaker)));
 json row=JsonObject();row=JsonObjectSet(row,"id",JsonInt(index));row=JsonObjectSet(row,"kind",JsonString(kind));
 row=JsonObjectSet(row,"approved",JsonInt(1));row=JsonObjectSet(row,"text",JsonString(source));
 row=JsonObjectSet(row,"display_token",JsonInt(token));
 json texts=JsonArray();texts=JsonArrayInsert(texts,row);e=JsonObjectSet(e,"texts",texts);
 SetLocalString(pc,key+"_request",JsonDump(e));SetLocalInt(pc,key+"_seq",RWI(e,"seq"));RWEmit(e);
}

void RWTrNodeVisible(string resource,string kind,int index,int token)
{
 if(!NWNX_Core_PluginExists("NWNX_Dialog") || !NWNX_Core_PluginExists("NWNX_Player"))return;
 if(GetIsPC(OBJECT_SELF) || GetIsDMPossessed(OBJECT_SELF) || GetLocalInt(OBJECT_SELF,"rw_no_translate"))return;
 string source=NWNX_Dialog_GetCurrentNodeText(0,0);
 // Do not resolve dynamic/custom tokens (which may contain player-authored text).
 // Such lines keep the native display and do not go to the provider in this preview.
 if(source=="" || GetStringLength(source)>2000 || FindSubString(source,"<")>=0)return;
 if(NWNX_Core_PluginExists("NWNX_RWTranslation"))
 {
  // Register an approved node without changing its text or requesting an LLM.
  // Each actual viewer (including spectators) is handled at native delivery.
  if(RWTrNativeInt("GetProtocol")==1)RWTrNativeRegister(OBJECT_SELF,resource,kind,index,token,source);
  return;
 }
 object pc=GetPCSpeaker();
 if(!GetIsPC(pc) || GetIsDMPossessed(pc) || !GetLocalInt(pc,"rw_tr_enabled"))return;
 string key=RWTrNodeKey(token);RWTrNodeRemember(pc,key,source);
 string language=GetLocalString(pc,"rw_tr_language");int tick=GetLocalInt(GetModule(),"rw_tick");
 string translated=GetLocalString(pc,key+"_value");
 if(GetLocalString(pc,key+"_language")!=language)translated="";
 if(translated!="" && RWTrNodePrivateView(pc))
 {
  // Initialize only the interacting player's token. Native private dialogue
  // remains native; no server-wide custom-token broadcast is made.
  NWNX_Player_SetCustomToken(pc,token,translated);
  int clientLanguage=NWNX_Player_GetLanguage(pc),gender;
  for(gender=0;gender<2;gender++)
  {
   string slot=key+"_o"+IntToString(clientLanguage)+"_"+IntToString(gender);
   SetLocalInt(OBJECT_SELF,slot,TRUE);SetLocalString(OBJECT_SELF,slot,NWNX_Dialog_GetCurrentNodeText(clientLanguage,gender));
   NWNX_Dialog_SetCurrentNodeText("<CUSTOM"+IntToString(token)+">",clientLanguage,gender);
  }
 }
 RWTrNodeRequest(pc,OBJECT_SELF,resource,kind,index,token,source);
}

void RWTrNodeReply(json cmd)
{
 object pc=StringToObject(RWS(cmd,"player"));json texts=JsonObjectGet(cmd,"texts");
 if(!GetIsPC(pc) || RWS(cmd,"world")!=RWWorld() || RWS(cmd,"session")!=GetLocalString(GetModule(),"rw_session")
  || RWS(cmd,"token")!=GetLocalString(pc,"rw_tr_token") || RWI(cmd,"expires")<GetLocalInt(GetModule(),"rw_tick")
  || !GetLocalInt(pc,"rw_tr_enabled") || !RWI(cmd,"enabled") || RWS(cmd,"language")!=GetLocalString(pc,"rw_tr_language")
  || JsonGetLength(texts)!=1)return;
 json row=JsonArrayGet(texts,0);string key=RWTrNodeKey(RWI(row,"display_token"));
 if(RWI(cmd,"seq")!=GetLocalInt(pc,key+"_seq"))return;
 json request=JsonParse(GetLocalString(pc,key+"_request"));json original=JsonArrayGet(JsonObjectGet(request,"texts"),0);
 object npc=StringToObject(RWS(request,"speaker"));
 if(!GetIsObjectValid(npc) || GetLocalInt(npc,"rw_no_translate") || RWS(cmd,"dialogue")!=RWS(request,"dialogue")
  || RWS(cmd,"speaker")!=RWS(request,"speaker") || RWI(row,"id")!=RWI(original,"id") || RWS(row,"kind")!=RWS(original,"kind")
  || RWS(row,"text")!=RWS(original,"text") || RWS(row,"text")!=GetLocalString(pc,key))return;
 SetLocalString(pc,key+"_value",RWS(row,"translated"));SetLocalString(pc,key+"_language",RWS(cmd,"language"));
 SetLocalInt(pc,key+"_time",GetLocalInt(GetModule(),"rw_tick"));
 // Deliberately do not rewrite an already displayed choice. Next visit uses it.
}
