// Isolated server fixture only. It never changes the live world or calls an LLM.
#include "rw_tr_nodes"
void Check(string label,int ok)
{WriteTimestampedLogEntry("RW_INV_TEST "+label+" "+(ok?"PASS":"FAIL"));}
void Run(string resource,object partner)
{
 object m=GetModule();SetLocalObject(m,"td_actor",OBJECT_SELF);SetLocalObject(m,"td_partner",partner);
 SetLocalInt(m,"td_gate_calls",0);SetLocalInt(m,"td_denied",0);SetLocalInt(m,"td_visible",0);
 SetLocalInt(m,"td_action_calls",0);SetLocalInt(m,"td_gate_ok",0);SetLocalInt(m,"td_action_ok",0);
 Check(resource+"_opens",BeginConversation(resource,partner));
 Check(resource+"_original_condition_context_and_params",GetLocalInt(m,"td_gate_ok"));
 Check(resource+"_denied_start_checked",GetLocalInt(m,"td_denied")>0);
 if(resource=="td_original")
 {
  SetLocalInt(m,"td_baseline_calls",GetLocalInt(m,"td_gate_calls"));
  SetLocalInt(m,"td_baseline_actions",GetLocalInt(m,"td_action_calls"));
 }
 else
 {
  Check("same_number_of_condition_executions",GetLocalInt(m,"td_gate_calls")==GetLocalInt(m,"td_baseline_calls"));
  Check("same_number_of_action_executions",GetLocalInt(m,"td_action_calls")==GetLocalInt(m,"td_baseline_actions"));
  Check("only_allowed_start_reaches_translation_hook",GetLocalInt(m,"td_visible")==GetLocalInt(m,"td_gate_calls"));
  Check("npc_only_conversation_never_requests_translation",GetLocalInt(partner,"rw_tr_nodes_seq")==0);
  if(NWNX_Core_PluginExists("NWNX_RWTranslation"))
   Check("native_adapter_registered_approved_node",RWTrNativeInt("TestRegisteredCount")>0);
  WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
 }
}
void main()
{
 Check("dialog_plugin",NWNX_Core_PluginExists("NWNX_Dialog"));
 Check("util_plugin",NWNX_Core_PluginExists("NWNX_Util"));
 if(NWNX_Core_PluginExists("NWNX_RWTranslation"))
  WriteTimestampedLogEntry(RWTrNativeString("TestRun"));
 object guide=GetObjectByTag("rw_tr_guide");location here=GetLocation(guide);
 object a=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",here),b=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",here);
 object c=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",here),d=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",here);
 int i;for(i=0;i<65;i++)RWTrNodeRemember(a,RWTrNodeKey(5000000+i),"Source");
 Check("working_set_is_bounded",GetLocalString(a,RWTrNodeKey(5000000))=="" && GetLocalString(a,RWTrNodeKey(5000064))=="Source");
 SetLocalString(a,"rw_td_5000064_value","Old translation");RWTrNodeRemember(a,"rw_td_5000064","Changed source");
 Check("changed_source_clears_stale_native_translation",GetLocalString(a,"rw_td_5000064_value")=="");
 AssignCommand(a,Run("td_original",b));AssignCommand(c,Run("td_prepared",d));
}
