#include "rw_translate"
void main()
{
 object pc=NuiGetEventPlayer();int token=NuiGetEventWindow();
 if(NuiGetEventType()!="click")return;
 string window=NuiGetWindowId(pc,token),element=NuiGetEventElement();
 if(window=="rwtranslation" && element=="original")
 {
  int original=!JsonGetInt(NuiGetBind(pc,token,"showing_original"));
  NuiSetBind(pc,token,"showing_original",JsonInt(original));
  NuiSetBind(pc,token,"body",NuiGetBind(pc,token,original?"original":"translated"));
  NuiSetBind(pc,token,"toggle_label",JsonString(original?"Show translated text":"Show original text"));return;
 }
 if(window!="rwlanguage" || !GetLocalInt(pc,"rw_tr_loaded"))return;
 int enabled=GetLocalInt(pc,"rw_tr_preference");string language=GetLocalString(pc,"rw_tr_language");
 if(element=="toggle")enabled=!enabled;
 else if(GetStringLeft(element,5)=="lang_")
 {
  string selected=GetSubString(element,5,2);int found=FALSE,i;
  json langs=JsonParse(GetLocalString(pc,"rw_tr_languages"));
  for(i=0;i<JsonGetLength(langs);i++)if(JsonGetString(JsonArrayGet(langs,i))==selected)found=TRUE;
  if(!found){NuiSetBind(pc,token,"status",JsonString("That language is not enabled by the server."));return;}
  language=selected;
 }
 else return;
 // Stop display immediately while a changed preference is being saved.
 SetLocalInt(pc,"rw_tr_enabled",FALSE);RWTrClose(pc);RWTrClearNames(pc);
 DeleteLocalInt(pc,"rw_tr_dialog_pending");
 SetLocalInt(pc,"rw_tr_loaded",FALSE);NuiSetBind(pc,token,"status",JsonString("Saving preference..."));
 json e=RWTrEvent(pc,"translation_preference");e=JsonObjectSet(e,"enabled",JsonInt(enabled));e=JsonObjectSet(e,"language",JsonString(language));RWEmit(e);
}
