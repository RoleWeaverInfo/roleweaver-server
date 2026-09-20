#include "rq_inc"
void main()
{
 object pc=GetLastUsedBy();if(!GetIsPC(pc)||GetIsDM(pc))return;
 SendMessageToPC(pc,"KINGDOM OF ROLE WEAVER - INVESTIGATOR'S NOTICEBOARD");
 SendMessageToPC(pc,"THE MISSING CARAVAN: Speak to Captain Beran about your duty. Question the innkeeper, merchant, wizard, cleric and Holt about the caravan. Discuss what witnesses saw; relevant accounts are recorded as they tell you. Type /case for your notes. Ask Beran for a royal audience when ready.");
 SendMessageToPC(pc,"CONVERSATION: Stand close and use Talk To, or address the NPC by name. Continue naturally once selected. Say goodbye to end the conversation.");
 SendMessageToPC(pc,"SHOPPING: Ask Merchant 'Show me your wares', ask about a weapon, then 'Could I have a discount?' Haggling uses a game roll and a small capped discount. Reopen the shop after a successful haggle. Buy an item, then ask what stock remains.");
 SendMessageToPC(pc,"MOVEMENT: Ask the innkeeper 'Lead me to the visitor table', the wizard 'Show me your study', or the cleric 'Take me to the shrine'. Try 'Walk to the merchant stall' and 'Return home'. Only approved destinations work.");
 SendMessageToPC(pc,"EXPERTS AND MEMORY: Ask Aldren how Magic Missile works, Meriel about mercy or local faith, and the innkeeper about daily life. Introduce yourself and share a detail, then return later and ask whether they remember.");
 SendMessageToPC(pc,"SOLVING THE CASE: Explain who you accuse and two recorded witness accounts to the King, across several messages if needed. He listens and asks questions naturally. There are no dialogue menus. An incomplete or wrong case can be retried. Reward: 100 gold once per visit.");
}
