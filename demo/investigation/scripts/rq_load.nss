void main()
{
 SetLocalString(GetModule(),"rw_story_context_hook","rq_context");
 SetLocalString(GetModule(),"rw_story_reply_hook","rq_reply");
 ExecuteScript("rw_worldload",GetModule());
 DelayCommand(2.0,ExecuteScript("rq_setup",GetModule()));
}
