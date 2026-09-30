// Isolated server fixture; never install as a live module's load handler.
#include "rw_tr_dialog"
#include "rw_tr_names"
void Check(string name,int passed)
{WriteTimestampedLogEntry("RW_INV_TEST " + name + (passed?" PASS":" FAIL"));}
void CheckFullDialogue(object other)
{
 // The engine loads ReplyList only for a full conversation. A one-liner or
 // a GFF round trip does not detect missing required reply fields (e.g. Delay).
 // NPC-to-NPC starts exercise that loader without needing a connected client.
 Check("native_full_dialogue_opens",BeginConversation(RW_TR_DEMO_RESREF,other));
 WriteTimestampedLogEntry("RW_INV_TEST FINISHED");
}
void main()
{
 object chest=GetObjectByTag("rq_testchest");
 Check("fixture_chest",GetIsObjectValid(chest));
 DeleteLocalInt(chest,"rw_translate");DeleteLocalInt(chest,"rw_no_translate");
 Check("unmarked_included_by_default",RWTrEligible(chest));
 RWTrSetExcluded(chest,TRUE);
 Check("dm_exclusion",!RWTrEligible(chest));
 SetLocalInt(chest,"rw_translate",TRUE);
 Check("legacy_allow_cannot_override_exclusion",!RWTrEligible(chest));
 RWTrSetExcluded(chest,FALSE);
 Check("dm_reinclude",RWTrEligible(chest));
 DeleteLocalInt(chest,"rw_translate");
 object item=CreateItemOnObject("nw_it_mpotion001",chest);
 Check("fixture_item",GetIsObjectValid(item));
 SetIdentified(item,FALSE);
 Check("unidentified_excluded",!RWTrEligible(item));
 SetIdentified(item,TRUE);Check("identified_item_default",RWTrEligible(item));
 RWTrSetExcluded(item,TRUE);Check("identified_item_excluded",!RWTrEligible(item));
 RWTrSetExcluded(item,FALSE);Check("identified_item_reincluded",RWTrEligible(item));
 Check("invalid_object_excluded",!RWTrEligible(OBJECT_INVALID));
 object creature=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",GetLocation(chest));
 Check("fixture_creature",GetIsObjectValid(creature));
 Check("ordinary_npc_description_included",RWTrEligible(creature));
 SetLocalString(creature,"rw_id","test_guard");
 SetLocalString(creature,"rw_personality","Private information, not public Examine text.");
 Check("ai_npc_description_included",RWTrEligible(creature));
 RWTrSetExcluded(creature,TRUE);Check("npc_description_dm_exclusion",!RWTrEligible(creature));
 RWTrSetExcluded(creature,FALSE);Check("npc_description_reincluded",RWTrEligible(creature));
 Check("native_object_id_round_trip",StringToObject(ObjectToString(creature))==creature);
 // Public PC descriptions use the same engine description/JSON transport. A
 // real player is still needed to playtest the per-viewer NUI window itself.
 string biography="A traveller from the coast. ";int part;
 for(part=0;part<7;part++)biography+=biography;
 biography+="\n\nThey wear a blue cloak.";
 SetDescription(creature,biography);
 Check("long_description_engine_round_trip",GetStringLength(biography)>2000 && GetDescription(creature)==biography);
 json profile=JsonObjectSet(JsonObject(),"description",JsonString(GetDescription(creature)));
 Check("long_description_json_round_trip",RWS(JsonParse(JsonDump(profile)),"description")==biography);
 string name=GetName(chest),description=GetDescription(chest);
 SetLocalInt(creature,"rw_tr_seq",5);SetLocalObject(creature,"rw_tr_object",chest);
 RWTrExamine(creature,chest);
 Check("source_unchanged",GetName(chest)==name && GetDescription(chest)==description);
 Check("new_examine_invalidates_old",GetLocalInt(creature,"rw_tr_seq")==6 && !GetIsObjectValid(GetLocalObject(creature,"rw_tr_object")));
 json unicode=JsonParse("{\"text\":\"Fran\\u00e7ais: tr\\u00e8s bien\"}");
 json layout=NuiText(JsonObjectGet(unicode,"text"),TRUE,2);
 Check("unicode_json_layout",JsonGetType(layout)==JSON_TYPE_OBJECT && JsonGetType(JsonParse(JsonDump(layout)))==JSON_TYPE_OBJECT);
 json payload=RWTrEvent(creature,"translation_examine");
 Check("request_sequence",RWI(payload,"seq")==7 && RWS(payload,"token")!="");
 json names=RWTrEvent(creature,"translation_names");
 Check("name_sequence_is_separate",RWI(names,"seq")==1 && GetLocalInt(creature,"rw_tr_seq")==7);
 Check("name_auto_default",RWTrNameMode(chest)=="auto");
 SetLocalInt(chest,"rw_tr_name_mode",1);
 Check("name_preserve_excluded",RWTrNameMode(chest)=="preserve" && !RWTrNameEligible(creature,chest));
 SetLocalInt(chest,"rw_tr_name_mode",2);
 Check("name_label_policy",RWTrNameMode(chest)=="translate" && RWTrNameEligible(creature,chest));
 RWTrSetExcluded(chest,TRUE);
 Check("exclusion_overrides_name_policy",!RWTrNameEligible(creature,chest));
 RWTrSetExcluded(chest,FALSE);DeleteLocalInt(chest,"rw_tr_name_mode");
 SetLocalInt(creature,"rw_tr_enabled",TRUE);SetLocalInt(creature,"rw_tr_name_count",1);
 SetLocalObject(creature,"rw_tr_name_0",chest);SetLocalString(creature,"rw_tr_name_0",name);
 SetLocalString(creature,"rw_tr_name_0_mode","auto");SetLocalString(creature,"rw_tr_name_0_display","Coffre");
 Check("observer_alias",RWTrNameAlias(creature,chest)=="Coffre");
 SetLocalString(creature,"rw_tr_name_0","Old source");
 Check("changed_source_rejects_alias",RWTrNameAlias(creature,chest)=="");
 RWTrClearNames(creature);
 Check("clears_tracked_aliases",GetLocalInt(creature,"rw_tr_name_count")==0 && GetLocalString(creature,"rw_tr_name_0_display")=="");
 Check("name_cleanup_leaves_shared_source",GetName(chest)==name && GetDescription(chest)==description);
 json texts=RWTrDemoTexts();
 Check("dialogue_manifest",JsonGetLength(texts)==21 && RWS(JsonArrayGet(texts,0),"kind")=="dialogue_entry" && RWS(JsonArrayGet(texts,4),"kind")=="dialogue_reply");
 object guide=GetObjectByTag("rw_tr_guide");
 Check("ordinary_guide_in_module",GetIsObjectValid(guide) && GetName(guide)=="Royal Guide");
 Check("ordinary_guide_not_ai",GetLocalString(guide,"rw_id")=="" && GetLocalString(guide,"rw_mode")=="");
 Check("ordinary_guide_dialogue_handler",GetEventScript(guide,EVENT_SCRIPT_CREATURE_ON_DIALOGUE)=="rw_tr_talk");
 SetLocalInt(guide,"rw_tr_demo_lock",TRUE);RWTrDlgRelease(guide);
 Check("ordinary_guide_cleanup_keeps_no_ai_mode",GetLocalString(guide,"rw_mode")=="" && GetLocalInt(guide,"rw_epoch")==0);
 SetLocalInt(creature,"rw_tr_demo_ai",TRUE);
 SetLocalInt(creature,"rw_tr_demo_lock",TRUE);SetLocalInt(creature,"rw_tr_demo_epoch",2);
 SetLocalInt(creature,"rw_epoch",3);SetLocalString(creature,"rw_mode","dm");
 RWTrDlgRelease(creature);
 Check("dialogue_cleanup_preserves_new_dm_mode",GetLocalString(creature,"rw_mode")=="dm" && !GetLocalInt(creature,"rw_tr_demo_lock"));
 SetLocalInt(creature,"rw_tr_demo_lock",TRUE);SetLocalString(creature,"rw_mode","paused");SetLocalInt(creature,"rw_tr_demo_ai",TRUE);
 RWTrDlgRelease(creature);
 Check("dialogue_cleanup_respects_new_pause",GetLocalString(creature,"rw_mode")=="paused");
 SetLocalInt(creature,"rw_tr_demo_lock",TRUE);SetLocalObject(creature,"rw_tr_demo_pc",creature);
 SetLocalObject(chest,"rw_tr_dialog_npc",creature);RWTrDlgFinish(chest);
 Check("old_dialogue_callback_cannot_release_other_player",GetLocalInt(creature,"rw_tr_demo_lock"));
 SetLocalObject(creature,"rw_tr_dialog_npc",creature);RWTrDlgFinish(creature);
 Check("dialogue_owner_can_release_lock",!GetLocalInt(creature,"rw_tr_demo_lock") && !GetIsObjectValid(GetLocalObject(creature,"rw_tr_dialog_npc")));
 object first=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",GetLocation(chest));
 object second=CreateObject(OBJECT_TYPE_CREATURE,"rw_base",GetLocation(chest));
 AssignCommand(first,CheckFullDialogue(second));
}
