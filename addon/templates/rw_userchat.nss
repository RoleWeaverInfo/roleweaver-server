// NEW/EMPTY modules: assign to Module Properties > Events > OnPlayerChat.
// EXISTING worlds: do NOT replace your current chat/filter handler with this.
// Call rw_modulechat from inside its approved-message path instead.
void main()
{
    ExecuteScript("rw_modulechat", OBJECT_SELF);
}
