// Optional recipient-specific DLG text adapter for NWNX 8193.37.17.
//
// Never edit the active dialogue or resend/re-evaluate a game choice. Observe
// prepared nodes when their original condition passes, then substitute only a
// COPY of text which the engine is already sending to a particular recipient.
// Chat, floating speech, journals and other message types are not hooked.
// The callback reads the game-side cache and queues Redis work; it never waits
// for an LLM. If any association is uncertain, send the original unchanged.
#include "nwnx.hpp"
#include "API/CNWSDialog.hpp"
#include "API/CNWSDialogEntry.hpp"
#include "API/CNWSDialogReply.hpp"
#include "API/CNWSMessage.hpp"
#include "API/CNWSObject.hpp"
#include "API/CNWSPlayer.hpp"
#include "API/CServerExoApp.hpp"
#include "API/CAppManager.hpp"
#include <algorithm>
#include <map>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
using namespace NWNXLib;
using namespace NWNXLib::API;
#ifdef RW_TRANSLATION_TESTS
#include <functional>
// Test seams exist only in the isolated-server build, never the installed plugin.
std::function<bool(uint32_t, ObjectID&, int&)> testRecipient;
std::function<void()> testCallback;
std::function<int(uint32_t, const CExoLocString*, uint32_t*, uint32_t, uint32_t,
                  ObjectID, uint8_t, int, uint32_t, int)> testReplies;
std::function<int(uint32_t, ObjectID, ObjectID, CExoLocString, ObjectID, uint8_t)> testEntry;
std::function<int(uint32_t, uint32_t, uint32_t, CExoLocString, ObjectID, uint8_t, int)> testChosen;
#endif

namespace {
constexpr size_t MaxDialogs = 256, MaxNodes = 512, MaxReplies = 256;
struct Node {
    std::string resource, kind, source;
    int index, token;
    ObjectID speaker;
};
struct Dialog {
    ObjectID owner;
    std::map<std::pair<std::string, int>, Node> nodes;
};
struct Frame { CNWSDialog* dialog; CNWSObject* owner; };
struct Delivery { Node node; ObjectID player; std::string replacement; };
// NWN invokes these hooks on its game thread. Stack scopes protect nested
// conversations started by a condition/action script from mixing their context.
std::unordered_map<CNWSDialog*, Dialog> dialogs;
std::vector<Frame> frames;
Delivery* currentDelivery = nullptr;
struct FrameScope {
    FrameScope(CNWSDialog* d, CNWSObject* o) { frames.push_back({d, o}); }
    ~FrameScope() { frames.pop_back(); }
};
struct DeliveryScope {
    Delivery* previous;
    explicit DeliveryScope(Delivery* d) : previous(currentDelivery) { currentDelivery = d; }
    ~DeliveryScope() { currentDelivery = previous; }
};

std::string English(const CExoLocString& text) {
    CExoString value;
    text.GetString(0, &value, 0);
    return value.CStr() ? value.CStr() : "";
}
bool PlainSource(const std::string& s) {
    return !s.empty() && s.size() <= 2000 && s.find('<') == std::string::npos;
}
bool Resource(const std::string& s) {
    return !s.empty() && s.size() <= 16 && std::all_of(s.begin(), s.end(), [](char c) {
        return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_';
    });
}
std::optional<Node> Match(const CExoLocString& text, const char* kind) {
    if (frames.empty()) return {};
    auto state = dialogs.find(frames.back().dialog);
    if (state == dialogs.end()) return {};
    auto source = English(text);
    if (!PlainSource(source)) return {};
    std::optional<Node> found;
    for (const auto& pair : state->second.nodes) {
        const auto& n = pair.second;
        if (n.kind != kind || n.source != source) continue;
        // An ambiguous mapping across resources/speakers must stay native.
        // Identical text in two nodes of the same resource shares a cache value.
        if (found && (found->resource != n.resource || found->speaker != n.speaker)) return {};
        found = n;
    }
    return found;
}

// Return a fresh localized string, leaving both the shared DLG and the caller's
// original string untouched. The engine still controls which recipients see it.
std::optional<CExoLocString> Translate(uint32_t recipient, const CExoLocString& original,
                                      const char* kind, uint8_t gender) {
    const auto node = Match(original, kind);
    if (!node || currentDelivery) return {};
    ObjectID playerObject;
    int language;
#ifdef RW_TRANSLATION_TESTS
    if (testRecipient) {
        if (!testRecipient(recipient, playerObject, language)) return {};
    } else
#endif
    {
        auto* server = Globals::AppManager()->m_pServerExoApp;
        auto* player = server->GetClientObjectByPlayerId(recipient);
        if (!player || !player->GetGameObject()) return {};
        playerObject = player->m_oidNWSObject;
        language = server->GetPlayerLanguage(recipient);
    }
    Delivery delivery{*node, playerObject, ""};
    DeliveryScope scope(&delivery);
#ifdef RW_TRANSLATION_TESTS
    if (testCallback) testCallback(); else
#endif
    Utils::ExecuteScript("rw_tr_send", delivery.player);
    if (delivery.replacement.empty()) return {};
    CExoLocString result;
    result.AddString(language, CExoString(delivery.replacement), gender);
    return result;
}

Hooks::Hook startHook, entryContextHook, replyContextHook, choiceContextHook, cleanupHook;
Hooks::Hook entryHook, repliesHook, chosenHook;

uint32_t Start(CNWSDialog* d, CNWSObject* owner) {
    // Cleanup normally erases this state. This reset also handles a reused DLG.
    dialogs.erase(d);
    if (dialogs.size() < MaxDialogs) dialogs.emplace(d, Dialog{owner->m_idSelf, {}});
    FrameScope scope(d, owner);
    return startHook->CallOriginal<uint32_t>(d, owner);
}
int EntryContext(CNWSDialog* d, CNWSObject* owner, uint32_t guiOnly, uint32_t index, int hello) {
    FrameScope scope(d, owner);
    return entryContextHook->CallOriginal<int>(d, owner, guiOnly, index, hello);
}
int ReplyContext(CNWSDialog* d, CNWSObject* owner, uint32_t guiOnly) {
    FrameScope scope(d, owner);
    return replyContextHook->CallOriginal<int>(d, owner, guiOnly);
}
int ChoiceContext(CNWSDialog* d, uint32_t player, CNWSObject* owner, uint32_t index, int escape, uint32_t entry) {
    FrameScope scope(d, owner);
    return choiceContextHook->CallOriginal<int>(d, player, owner, index, escape, entry);
}
void Cleanup(CNWSDialog* d) {
    dialogs.erase(d);
    cleanupHook->CallOriginal<void>(d);
}
int Entry(CNWSMessage* message, uint32_t recipient, ObjectID owner, ObjectID speaker,
          CExoLocString text, ObjectID tokenTarget, uint8_t gender) {
    auto translated = Translate(recipient, text, "dialogue_entry", gender);
#ifdef RW_TRANSLATION_TESTS
    if (testEntry) return testEntry(recipient, owner, speaker,
        translated ? *translated : text, tokenTarget, gender);
#endif
    return entryHook->CallOriginal<int>(message, recipient, owner, speaker,
        translated ? *translated : text, tokenTarget, gender);
}
int Replies(CNWSMessage* message, uint32_t recipient, CExoLocString* texts, uint32_t* indices,
            uint32_t count, uint32_t inactive, ObjectID tokenTarget, uint8_t gender,
            int end, uint32_t entry, int noZoom) {
    // This is the already-filtered outgoing list. Keep every index, count,
    // inactive flag and timing argument exactly as supplied by the engine.
    std::vector<CExoLocString> copies;
    // The native arrays contain BOTH active and inactive replies. Never shorten
    // that array or overflow the sum; unsupported sizes take the original path.
    if (texts && count <= MaxReplies && inactive <= MaxReplies - count) {
        const uint32_t total = count + inactive;
        copies.reserve(total);
        for (uint32_t i = 0; i < total; ++i) {
            auto translated = Translate(recipient, texts[i], "dialogue_reply", gender);
            copies.push_back(translated ? *translated : texts[i]);
        }
    }
    auto* outgoing = copies.empty() ? texts : copies.data();
#ifdef RW_TRANSLATION_TESTS
    if (testReplies) return testReplies(recipient, outgoing, indices, count, inactive,
        tokenTarget, gender, end, entry, noZoom);
#endif
    return repliesHook->CallOriginal<int>(message, recipient, outgoing, indices,
        count, inactive, tokenTarget, gender, end, entry, noZoom);
}
int Chosen(CNWSMessage* message, uint32_t recipient, uint32_t index, uint32_t entry,
           CExoLocString text, ObjectID tokenTarget, uint8_t gender, int end) {
    auto translated = Translate(recipient, text, "dialogue_reply", gender);
#ifdef RW_TRANSLATION_TESTS
    if (testChosen) return testChosen(recipient, index, entry,
        translated ? *translated : text, tokenTarget, gender, end);
#endif
    return chosenHook->CallOriginal<int>(message, recipient, index, entry,
        translated ? *translated : text, tokenTarget, gender, end);
}
struct Install {
    Install() {
        startHook = Hooks::HookFunction(&CNWSDialog::GetStartEntry, &Start, Hooks::Order::VeryEarly);
        entryContextHook = Hooks::HookFunction(&CNWSDialog::SendDialogEntry, &EntryContext, Hooks::Order::VeryEarly);
        replyContextHook = Hooks::HookFunction(&CNWSDialog::SendDialogReplies, &ReplyContext, Hooks::Order::VeryEarly);
        choiceContextHook = Hooks::HookFunction(&CNWSDialog::HandleReply, &ChoiceContext, Hooks::Order::VeryEarly);
        cleanupHook = Hooks::HookFunction(&CNWSDialog::Cleanup, &Cleanup, Hooks::Order::VeryEarly);
        entryHook = Hooks::HookFunction(&CNWSMessage::SendServerToPlayerDialogEntry, &Entry);
        repliesHook = Hooks::HookFunction(&CNWSMessage::SendServerToPlayerDialogReplies, &Replies);
        chosenHook = Hooks::HookFunction(&CNWSMessage::SendServerToPlayerDialogReplyChosen, &Chosen);
    }
} install;
} // namespace

NWNX_EXPORT ArgumentStack RegisterNode(ArgumentStack&& args) {
    auto speaker = args.extract<ObjectID>();
    auto resource = args.extract<std::string>();
    auto kind = args.extract<std::string>();
    auto index = args.extract<int32_t>();
    auto token = args.extract<int32_t>();
    auto source = args.extract<std::string>();
    if (frames.empty() || !Resource(resource) || !PlainSource(source) || index < 0 || token < 100000)
        return 0;
    auto* d = frames.back().dialog;
    auto state = dialogs.find(d);
    if (state == dialogs.end() || state->second.owner != frames.back().owner->m_idSelf) return 0;
    const CExoLocString* native = nullptr;
    if (kind == "dialogue_entry" && static_cast<uint32_t>(index) < d->m_nEntries) native = &d->m_pEntries[index].m_sText;
    if (kind == "dialogue_reply" && static_cast<uint32_t>(index) < d->m_nReplies) native = &d->m_pReplies[index].m_sText;
    if (!native || English(*native) != source) return 0;
    auto key = std::make_pair(kind, index);
    if (state->second.nodes.size() >= MaxNodes && !state->second.nodes.count(key)) return 0;
    state->second.nodes.insert_or_assign(key, Node{resource, kind, source, index, token, speaker});
    return 1;
}
NWNX_EXPORT ArgumentStack GetProtocol(ArgumentStack&&) { return 1; }
NWNX_EXPORT ArgumentStack GetSource(ArgumentStack&&) { return currentDelivery ? currentDelivery->node.source : ""; }
NWNX_EXPORT ArgumentStack GetResource(ArgumentStack&&) { return currentDelivery ? currentDelivery->node.resource : ""; }
NWNX_EXPORT ArgumentStack GetKind(ArgumentStack&&) { return currentDelivery ? currentDelivery->node.kind : ""; }
NWNX_EXPORT ArgumentStack GetIndex(ArgumentStack&&) { return currentDelivery ? currentDelivery->node.index : -1; }
NWNX_EXPORT ArgumentStack GetToken(ArgumentStack&&) { return currentDelivery ? currentDelivery->node.token : -1; }
NWNX_EXPORT ArgumentStack GetSpeaker(ArgumentStack&&) { return currentDelivery ? currentDelivery->node.speaker : Constants::OBJECT_INVALID; }
NWNX_EXPORT ArgumentStack GetRecipient(ArgumentStack&&) { return currentDelivery ? currentDelivery->player : Constants::OBJECT_INVALID; }
NWNX_EXPORT ArgumentStack SetText(ArgumentStack&& args) {
    auto text = args.extract<std::string>();
    if (currentDelivery && !text.empty() && text.size() <= 24000 && text.find('<') == std::string::npos)
        currentDelivery->replacement = text;
    return {};
}
#ifdef RW_TRANSLATION_TESTS
#include "TranslationTests.inc"
#endif
