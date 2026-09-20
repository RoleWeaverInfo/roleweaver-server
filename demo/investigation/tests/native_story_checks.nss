#include "rq_inc"
void Check(int pass,string label){WriteTimestampedLogEntry("RQ_TEST "+label+": "+(pass?"PASS":"FAIL"));}
void Later()
{
 object m=GetModule(),guard=RWFind("rq_guard");
 Check(GetIsObjectValid(guard),"guard_bound");
 Check(GetLocalString(m,"rw_story_context_hook")=="rq_context","context_hook_installed");
 Check(GetLocalString(m,"rw_story_reply_hook")=="rq_reply","reply_hook_installed");
 SetLocalObject(m,"rw_story_pc",guard);SetLocalObject(m,"rw_story_npc",guard);
 SetLocalString(m,"rw_story_event","test");DeleteLocalString(m,"rw_story_context");
 ExecuteScript("rq_context",m);
 Check(GetLocalString(m,"rw_story_context")=="","nonplayer_context_rejected");
 RQAudience(OBJECT_INVALID,guard);
 object king=RWFind("rq_king");Check(GetIsObjectValid(king),"audience_spawns_king");
 RQAudience(OBJECT_INVALID,guard);Check(!GetIsObjectValid(GetObjectByTag("rq_king",1)),"no_duplicate_king");
 Check(!RQCanPresent(guard,king),"nonplayer_cannot_win");
 RQSet(guard,"accepted",1);RQSet(guard,"clues",31);RQSet(guard,"rewarded",1);
 object other=RWFind("rq_wizard");RQSet(other,"clues",2);
 SetLocalString(guard,"rq_story_token","old");RQResetVisit(guard);
 Check(RQGet(guard,"accepted")==0&&RQGet(guard,"clues")==0&&RQGet(guard,"rewarded")==0,"login_resets_investigation");
 Check(RQGet(other,"clues")==2,"reset_does_not_affect_other_player");
 Check(GetLocalString(guard,"rq_story_token")=="","old_proposal_invalidated");
 string visit=GetLocalString(guard,"rq_visit");RQResetVisit(guard);
 Check(visit!=""&&GetLocalString(guard,"rq_visit")!=visit,"reconnect_has_new_visit_id");
 json cmd=JsonObject();cmd=JsonObjectSet(cmd,"listener",JsonString(ObjectToString(guard)));
 cmd=JsonObjectSet(cmd,"story_action",JsonString("story:verdict_10"));cmd=JsonObjectSet(cmd,"story_token",JsonString("test"));
 SetLocalString(guard,"rq_story_token","test");SetLocalObject(guard,"rq_story_npc",king);
 SetLocalString(king,"rw_story_reply",JsonDump(cmd));ExecuteScript("rq_reply",king);
 Check(GetLocalString(guard,"rq_story_token")=="test","nonplayer_reply_rejected_before_commit");
}
void main()
{
 ExecuteScript("rq_load",GetModule());
 Check(RQVerdictMask("story:verdict_10",31)==10,"two_recorded_clues");
 Check(RQVerdictMask("story:verdict_10",2)==0,"uncollected_clue_rejected");
 Check(RQVerdictMask("story:verdict_2",31)==0,"one_clue_rejected");
 Check(RQVerdictMask("story:verdict_0",31)==0,"empty_evidence_rejected");
 Check(RQVerdictMask("story:verdict_32",63)==0,"unknown_bit_rejected");
 Check(RQVerdictMask("story:verdict_10extra",31)==0,"trailing_payload_rejected");
 Check(RQVerdictMask("story:verdict_010",31)==0,"noncanonical_mask_rejected");
 Check(RQVerdictMask("story:verdict_-1",31)==0,"negative_mask_rejected");
 Check(RQVerdictMask("give_gold",31)==0,"arbitrary_command_rejected");
 Check(RQVerdictMask("story:verdict_31",31)==31,"five_clues_accepted");
 DelayCommand(5.0,Later());
}
