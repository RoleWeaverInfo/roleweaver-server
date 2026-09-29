// Bounded per-player name overrides. Doors and items lack these NWNX APIs.
#include "rw_translate"
int RWTrNameEligible(object pc,object o)
{
 int type=GetObjectType(o);
 return GetIsObjectValid(o) && !GetIsPC(o) && !GetIsDMPossessed(o)
   && (type==OBJECT_TYPE_CREATURE || type==OBJECT_TYPE_PLACEABLE)
   && !GetLocalInt(o,"rw_no_translate") && RWTrNameMode(o)!="preserve"
   && GetArea(o)==GetArea(pc);
}
void RWTrNamesTick(object pc)
{
 if(!GetIsPC(pc) || GetIsDMPossessed(pc) || !NWNX_Core_PluginExists("NWNX_Player"))return;
 int count=GetLocalInt(pc,"rw_tr_name_count");
 if(!GetLocalInt(pc,"rw_tr_enabled"))
 {if(count)RWTrClearNames(pc);return;}
 if(GetLocalObject(pc,"rw_tr_name_area")!=GetArea(pc))
 {RWTrClearNames(pc);SetLocalObject(pc,"rw_tr_name_area",GetArea(pc));count=0;}
 int tick=GetLocalInt(GetModule(),"rw_tick");
 if(GetLocalInt(pc,"rw_tr_name_next")>tick)return;
 SetLocalInt(pc,"rw_tr_name_next",tick+5);
 int i;for(i=0;i<count;i++)
 {
  string key="rw_tr_name_"+IntToString(i);object old=GetLocalObject(pc,key);
  if(!RWTrNameEligible(pc,old) || GetName(old)!=GetLocalString(pc,key) || RWTrNameMode(old)!=GetLocalString(pc,key+"_mode"))
  {RWTrApplyName(pc,old,"");DeleteLocalObject(pc,key);}
 }
 json rows=JsonArray();int cursor=GetLocalInt(pc,"rw_tr_name_cursor");
 for(i=0;i<16;i++)
 {
  cursor++;object o=GetNearestObject(OBJECT_TYPE_CREATURE|OBJECT_TYPE_PLACEABLE,pc,cursor);
  if(!GetIsObjectValid(o) || cursor>128){cursor=0;break;}
  if(!RWTrNameEligible(pc,o) || !LineOfSightObject(pc,o))continue;
  if(GetObjectType(o)==OBJECT_TYPE_CREATURE && !GetObjectSeen(o,pc))continue;
  string name=GetName(o);if(name=="" || GetStringLength(name)>200)continue;
  json row=JsonObject();row=JsonObjectSet(row,"object",JsonString(ObjectToString(o)));
  row=JsonObjectSet(row,"object_type",JsonInt(GetObjectType(o)));row=JsonObjectSet(row,"player_character",JsonInt(0));
  row=JsonObjectSet(row,"resref",JsonString(GetResRef(o)));row=JsonObjectSet(row,"name_mode",JsonString(RWTrNameMode(o)));
  row=JsonObjectSet(row,"text",JsonString(name));row=JsonObjectSet(row,"approved",JsonInt(1));
  rows=JsonArrayInsert(rows,row);
 }
 SetLocalInt(pc,"rw_tr_name_cursor",cursor);
 if(!JsonGetLength(rows))return;
 json e=RWTrEvent(pc,"translation_names");e=JsonObjectSet(e,"texts",rows);RWEmit(e);
}
void RWTrNamesReply(json cmd)
{
 object pc=StringToObject(RWS(cmd,"player"));
 if(!GetIsPC(pc) || GetIsDMPossessed(pc) || !GetLocalInt(pc,"rw_tr_enabled") || !RWI(cmd,"enabled")
  || RWS(cmd,"world")!=RWWorld() || RWS(cmd,"session")!=GetLocalString(GetModule(),"rw_session")
  || RWS(cmd,"token")!=GetLocalString(pc,"rw_tr_token") || RWI(cmd,"seq")!=GetLocalInt(pc,"rw_tr_names_seq")
  || RWS(cmd,"language")!=GetLocalString(pc,"rw_tr_language") || RWI(cmd,"expires")<GetLocalInt(GetModule(),"rw_tick"))return;
 json rows=JsonObjectGet(cmd,"texts");if(JsonGetLength(rows)>16)return;
 int i;for(i=0;i<JsonGetLength(rows);i++)
 {
  json row=JsonArrayGet(rows,i);object o=StringToObject(RWS(row,"object"));
  if(!RWTrNameEligible(pc,o) || GetName(o)!=RWS(row,"text") || RWTrNameMode(o)!=RWS(row,"name_mode"))continue;
  string value=RWS(row,"translated");
  if(value=="" || value==GetName(o) || GetStringLength(value)>200)value="";
  int j,count=GetLocalInt(pc,"rw_tr_name_count"),slot=-1;
  for(j=0;j<count;j++)
  {
   object old=GetLocalObject(pc,"rw_tr_name_"+IntToString(j));
   if(old==o){slot=j;break;}
   if(!GetIsObjectValid(old) && slot<0)slot=j;
  }
  if(slot<0){if(count>=128)continue;slot=count;SetLocalInt(pc,"rw_tr_name_count",count+1);}
  string key="rw_tr_name_"+IntToString(slot);SetLocalObject(pc,key,o);
  SetLocalString(pc,key,GetName(o));SetLocalString(pc,key+"_mode",RWTrNameMode(o));
  SetLocalString(pc,key+"_display",value);RWTrApplyName(pc,o,value);
 }
}
