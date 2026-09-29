// Loaded-plugin evidence for the owner health panel. No player data is emitted.
// This helper has no dependency on Redis and can be tested in isolation.
#include "nwnx_core"
json RWHealthPlugin(json plugins, string name)
{
    return JsonObjectSet(plugins, name, JsonInt(NWNX_Core_PluginExists("NWNX_" + name)));
}
json RWHealth(json hello)
{
    json plugins = JsonObject();
    plugins = RWHealthPlugin(plugins, "Core");
    plugins = RWHealthPlugin(plugins, "Chat");
    plugins = RWHealthPlugin(plugins, "Events");
    plugins = RWHealthPlugin(plugins, "Redis");
    plugins = RWHealthPlugin(plugins, "Creature");
    plugins = RWHealthPlugin(plugins, "Player");
    plugins = RWHealthPlugin(plugins, "Item");
    plugins = RWHealthPlugin(plugins, "Dialog");
    plugins = RWHealthPlugin(plugins, "Util");
    plugins = RWHealthPlugin(plugins, "RWTranslation");
    int protocol = 0;
    if (NWNX_Core_PluginExists("NWNX_RWTranslation"))
    {
        NWNXCall("NWNX_RWTranslation", "GetProtocol");
        protocol = NWNXPopInt();
    }
    hello = JsonObjectSet(hello, "health_protocol", JsonInt(1));
    hello = JsonObjectSet(hello, "health_plugins", plugins);
    return JsonObjectSet(hello, "translation_protocol", JsonInt(protocol));
}
