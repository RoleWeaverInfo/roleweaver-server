#include "rw_inc"
#include "nwnx_chat"
#include "nwnx_events"
void main()
{
    object m = GetModule();
    if (GetLocalInt(m, "rw_started")) return;
    SetLocalInt(m, "rw_started", 1);
    SetLocalString(m, "rw_session", IntToString(Random(2000000000)) + "_" + IntToString(Random(2000000000)));
    if (RW_REGISTERS_CHAT) NWNX_Chat_RegisterChatScript("rw_chat");
    NWNX_Events_SubscribeEvent("NWNX_ON_DM_POSSESS_BEFORE", "rw_possess");
    NWNX_Events_SubscribeEvent("NWNX_ON_DM_POSSESS_FULL_POWER_BEFORE", "rw_possess");
    NWNX_Events_SubscribeEvent("NWNX_ON_STORE_REQUEST_BUY_BEFORE","rw_shop_evt");
    NWNX_Events_SubscribeEvent("NWNX_ON_STORE_REQUEST_BUY_AFTER","rw_shop_evt");
    NWNX_Events_SubscribeEvent("NWNX_ON_STORE_REQUEST_SELL_BEFORE","rw_shop_evt");
    NWNX_Events_SubscribeEvent("NWNX_ON_STORE_REQUEST_SELL_AFTER","rw_shop_evt");
    ExecuteScript("rw_tick", m);
    WriteTimestampedLogEntry("ROLEWEAVER: bridge initialized; NPCs require explicit DM binding and resume.");
}
