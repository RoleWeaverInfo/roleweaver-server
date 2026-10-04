// The service stores character preferences in its backed-up database. Locals are
// a session-bound cache, never persistence. The AI cannot write permissions.
#include "rw_cp_base"

json RWCPDefaultPrefs(int safe=FALSE)
{
    json p=JsonObject();p=JsonObjectSet(p,"version",JsonInt(2));
    p=JsonObjectSet(p,"listening",JsonInt(0));
    p=JsonObjectSet(p,"reply",JsonInt(1));p=JsonObjectSet(p,"tone",JsonInt(0));
    p=JsonObjectSet(p,"followups",JsonInt(!safe));p=JsonObjectSet(p,"movement",JsonInt(!safe));
    p=JsonObjectSet(p,"inventory",JsonInt(!safe));p=JsonObjectSet(p,"collect",JsonInt(!safe));
    return JsonObjectSet(p,"deliver",JsonInt(!safe));
}
int RWCPValidPrefs(json p)
{
    int version=RWI(p,"version");
    if(JsonGetType(p)!=JSON_TYPE_OBJECT || (version!=1 && version!=2)
        || JsonGetLength(p)!=(version==1?8:9))return FALSE;
    json keys=JsonParse("[\"version\",\"reply\",\"tone\",\"followups\",\"movement\",\"inventory\",\"collect\",\"deliver\",\"listening\"]");int i;
    for(i=0;i<(version==1?8:9);i++)
    {
        string key=JsonGetString(JsonArrayGet(keys,i));json v=JsonObjectGet(p,key);
        if(JsonGetType(v)!=JSON_TYPE_INTEGER)return FALSE;
        int limit=1;if(key=="reply" || key=="version")limit=2;if(key=="tone")limit=4;
        if(JsonGetInt(v)<0 || JsonGetInt(v)>limit)return FALSE;
    }
    return TRUE;
}
json RWCPPreferences(object owner)
{
    json p=JsonParse(GetLocalString(owner,"rw_cpp_value"));
    if(!RWCPPreferencesReady(owner) || !RWCPValidPrefs(p))return RWCPDefaultPrefs(TRUE);
    if(RWI(p,"version")==1){p=JsonObjectSet(p,"version",JsonInt(2));p=JsonObjectSet(p,"listening",JsonInt(0));}
    return p;
}
int RWCPPreference(object owner,string key) {return RWI(RWCPPreferences(owner),key);}
void RWCPRequestPrefs(object owner)
{
    if(!GetIsPC(owner) || GetIsDM(owner) || GetIsDMPossessed(owner) || GetIsPossessedFamiliar(owner))return;
    SetLocalInt(owner,"rw_cpp_requested",TRUE);
    string identity=RWCPSettingsIdentity(owner),session=GetLocalString(GetModule(),"rw_session"),generation=GetLocalString(GetModule(),"rw_cpp_generation");
    if(identity!=GetLocalString(owner,"rw_cpp_identity") || session!=GetLocalString(owner,"rw_cpp_session") || generation!=GetLocalString(owner,"rw_cpp_generation"))
    {
        DeleteLocalInt(owner,"rw_cpp_loaded");DeleteLocalInt(owner,"rw_cpp_next");DeleteLocalString(owner,"rw_cpp_pending");
        SetLocalString(owner,"rw_cpp_identity",identity);SetLocalString(owner,"rw_cpp_session",session);SetLocalString(owner,"rw_cpp_generation",generation);
    }
    if(RWCPPreferencesReady(owner) || generation=="" || GetLocalInt(owner,"rw_cpp_next")>GetLocalInt(GetModule(),"rw_tick"))return;
    string pending=GetLocalString(owner,"rw_cpp_pending");string request=IntToString(Random(2000000000))+"_"+IntToString(Random(2000000000));
    SetLocalString(owner,"rw_cpp_request",request);SetLocalInt(owner,"rw_cpp_next",GetLocalInt(GetModule(),"rw_tick")+5);
    json e=RWBase(pending==""?"companion_preferences_get":"companion_preferences_set",OBJECT_INVALID);
    e=JsonObjectSet(e,"player",JsonString(ObjectToString(owner)));e=JsonObjectSet(e,"owner",JsonString(RWCPOwnerKey(owner)));
    e=JsonObjectSet(e,"creature",JsonString("familiar:"+IntToString(GetFamiliarCreatureType(owner))));
    e=JsonObjectSet(e,"request",JsonString(request));e=JsonObjectSet(e,"generation",JsonString(generation));
    e=JsonObjectSet(e,"preferences_protocol",JsonInt(2));
    if(pending!="")e=JsonObjectSet(e,"preferences",JsonParse(pending));RWEmit(e);
}
int RWCPStorePrefs(object owner,json p)
{
    if(!GetIsPC(owner) || GetIsDM(owner) || GetIsDMPossessed(owner) || GetIsPossessedFamiliar(owner)
        || !RWCPPreferencesReady(owner) || !RWCPValidPrefs(p))return FALSE;
    SetLocalString(owner,"rw_cpp_pending",JsonDump(p));DeleteLocalInt(owner,"rw_cpp_loaded");DeleteLocalInt(owner,"rw_cpp_next");
    RWCPRequestPrefs(owner);return TRUE;
}
int RWCPAcceptPrefs(json cmd)
{
    object owner=StringToObject(RWS(cmd,"player"));json p=JsonObjectGet(cmd,"preferences");
    if(!GetIsPC(owner) || GetIsDM(owner) || !RWCPValidPrefs(p)
        || RWS(cmd,"owner")!=RWCPOwnerKey(owner) || RWS(cmd,"creature")!="familiar:"+IntToString(GetFamiliarCreatureType(owner))
        || RWS(cmd,"request")!=GetLocalString(owner,"rw_cpp_request") || RWS(cmd,"generation")!=GetLocalString(GetModule(),"rw_cpp_generation")
        || GetLocalString(owner,"rw_cpp_identity")!=RWCPSettingsIdentity(owner) || GetLocalString(owner,"rw_cpp_session")!=GetLocalString(GetModule(),"rw_session"))return FALSE;
    SetLocalString(owner,"rw_cpp_value",JsonDump(p));SetLocalInt(owner,"rw_cpp_loaded",TRUE);
    DeleteLocalString(owner,"rw_cpp_pending");DeleteLocalString(owner,"rw_cpp_request");return TRUE;
}
// Restrict existing server permissions; never grant an action the server lacks.
int RWCPIWorkAllowed(object owner,json work)
{
    if(!RWCPPreference(owner,"inventory"))return FALSE;
    string verb=RWS(work,"verb");
    if(verb=="exchange")return TRUE; // May open in place with movement disabled.
    if(!RWCPPreference(owner,"movement"))return FALSE;
    if(verb=="inspect" || verb=="take" || verb=="fetch" || verb=="pickup" || verb=="fetch_ground")
        return RWCPPreference(owner,"collect");
    if(verb=="give" && StringToObject(RWS(work,"target"))==owner)return TRUE;
    if(verb=="give" || verb=="swap")return RWCPPreference(owner,"deliver");
    return FALSE;
}
