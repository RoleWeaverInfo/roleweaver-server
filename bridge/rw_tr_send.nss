// Called only for a recipient to whom the engine is already sending DLG text.
// Never open a window, choose a reply, execute a quest, or wait for a provider.
#include "rw_tr_nodes"
void main()
{
 if(!NWNX_Core_PluginExists("NWNX_RWTranslation"))return;
 object pc=OBJECT_SELF,speaker=RWTrNativeObject("GetSpeaker");
 if(pc!=RWTrNativeObject("GetRecipient") || !GetIsPC(pc) || GetIsDMPossessed(pc)
  || !GetIsObjectValid(speaker) || GetIsPC(speaker) || GetIsDMPossessed(speaker)
  || GetLocalInt(speaker,"rw_no_translate") || !GetLocalInt(pc,"rw_tr_enabled"))return;
 string source=RWTrNativeString("GetSource"),resource=RWTrNativeString("GetResource"),kind=RWTrNativeString("GetKind");
 int index=RWTrNativeInt("GetIndex"),token=RWTrNativeInt("GetToken");
 if(source=="" || GetStringLength(source)>2000 || FindSubString(source,"<")>=0 || token<100000)return;
 string key=RWTrNodeKey(token);RWTrNodeRemember(pc,key,source);
 if(GetLocalString(pc,key+"_language")==GetLocalString(pc,"rw_tr_language"))
 {
  string translated=GetLocalString(pc,key+"_value");
  if(translated!="")RWTrNativeText(translated);
 }
 RWTrNodeRequest(pc,speaker,resource,kind,index,token,source);
}
