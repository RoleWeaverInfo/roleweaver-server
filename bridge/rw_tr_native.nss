// Optional NWNX_RWTranslation adapter. Check PluginExists before calling.
int RWTrNativeRegister(object speaker,string resource,string kind,int index,int token,string source)
{
 NWNXPushString(source);NWNXPushInt(token);NWNXPushInt(index);
 NWNXPushString(kind);NWNXPushString(resource);NWNXPushObject(speaker);
 NWNXCall("NWNX_RWTranslation","RegisterNode");return NWNXPopInt();
}
string RWTrNativeString(string field)
{NWNXCall("NWNX_RWTranslation",field);return NWNXPopString();}
int RWTrNativeInt(string field)
{NWNXCall("NWNX_RWTranslation",field);return NWNXPopInt();}
object RWTrNativeObject(string field)
{NWNXCall("NWNX_RWTranslation",field);return NWNXPopObject();}
void RWTrNativeText(string text)
{NWNXPushString(text);NWNXCall("NWNX_RWTranslation","SetText");}
