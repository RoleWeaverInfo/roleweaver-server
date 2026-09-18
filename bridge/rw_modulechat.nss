// Run from OnPlayerChat AFTER the world's existing handler.
#include "rw_chat_inc"
void main()
{
    string text = GetPCChatMessage();
    if (text == "") return;
    int channel = -1;
    if (GetPCChatVolume() == TALKVOLUME_TALK) channel = NWNX_CHAT_CHANNEL_PLAYER_TALK;
    RWHandleChat(GetPCChatSpeaker(), text, channel, TRUE);
}
