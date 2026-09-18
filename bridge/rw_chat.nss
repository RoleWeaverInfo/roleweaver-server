#include "rw_chat_inc"
void main()
{
    RWHandleChat(NWNX_Chat_GetSender(), NWNX_Chat_GetMessage(), NWNX_Chat_GetChannel(), FALSE);
}
