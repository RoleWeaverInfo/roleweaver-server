// Compiled ONLY with RW_TRANSLATION_TESTS. Run in an isolated native server.
// Simulate recipients/transport; all copying and matching uses production hooks
// and the installed engine's real CExoLocString implementation.
NWNX_EXPORT ArgumentStack TestRegisteredCount(ArgumentStack&&) {
    int count = 0;
    for (const auto& pair : dialogs) count += pair.second.nodes.size();
    return count;
}
NWNX_EXPORT ArgumentStack TestRun(ArgumentStack&&) {
    int failures = 0, calls = 0;
    std::string report;
    auto check = [&](const char* label, bool ok) {
        LOG_INFO("RW_INV_TEST native_%s %s", label, ok ? "PASS" : "FAIL");
        report += std::string("RW_INV_TEST native_") + label + (ok ? " PASS\n" : " FAIL\n");
        if (!ok) ++failures;
    };
    auto text = [](const char* s) {
        CExoLocString value; value.AddString(0, CExoString(s), 0); return value;
    };
    // Opaque keys: no native object is fabricated or dereferenced.
    int key1 = 0, key2 = 0;
    auto* d = reinterpret_cast<CNWSDialog*>(&key1);
    auto* other = reinterpret_cast<CNWSDialog*>(&key2);
    dialogs.emplace(d, Dialog{10, {}});
    auto& nodes = dialogs.at(d).nodes;
    nodes.emplace(std::make_pair("dialogue_entry", 0), Node{"quest", "dialogue_entry", "Welcome", 0, 100000, 10});
    nodes.emplace(std::make_pair("dialogue_reply", 0), Node{"quest", "dialogue_reply", "Buy", 0, 100001, 10});
    testRecipient = [](uint32_t id, ObjectID& pc, int& lang) {
        pc = id + 100; lang = 0; return id != 9;
    };
    testCallback = [&] {
        ++calls;
        if (currentDelivery->player == 101) currentDelivery->replacement = "FR " + currentDelivery->node.source;
        if (currentDelivery->player == 102) currentDelivery->replacement = "DE " + currentDelivery->node.source;
    };
    auto welcome = text("Welcome"), buy = text("Buy");
    {
        FrameScope frame(d, nullptr);
        for (uint32_t id : {1, 2, 3, 9}) {
            std::string expected = id == 1 ? "FR Welcome" : id == 2 ? "DE Welcome" : "Welcome";
            testEntry = [&](uint32_t recipient, ObjectID owner, ObjectID speaker, CExoLocString value, ObjectID target, uint8_t gender) {
                check("entry_recipient_text_and_arguments", recipient == id && owner == 10 && speaker == 11
                    && target == 12 && gender == 1 && English(value) == expected);
                return 73;
            };
            check("entry_return_preserved", Entry(nullptr, id, 10, 11, welcome, 12, 1) == 73);
        }
        check("no_mutation_of_original_entry", English(welcome) == "Welcome");
        CExoLocString rows[] = {buy, text("Unavailable secret"), text("Goodbye")};
        uint32_t indices[] = {5, 7, 99};
        testReplies = [&](uint32_t id, const CExoLocString* values, uint32_t* ids, uint32_t count,
                          uint32_t inactive, ObjectID target, uint8_t gender, int end, uint32_t entry, int zoom) {
            check("replies_active_and_inactive_copy", count == 1 && inactive == 2 && values != rows
                && English(values[0]) == "FR Buy" && English(values[1]) == "Unavailable secret" && English(values[2]) == "Goodbye");
            check("replies_indices_and_arguments_unchanged", id == 1 && ids == indices && ids[0] == 5 && ids[1] == 7 && ids[2] == 99
                && target == 12 && gender == 0 && end == 1 && entry == 42 && zoom == 1);
            return 74;
        };
        check("replies_return_preserved", Replies(nullptr, 1, rows, indices, 1, 2, 12, 0, 1, 42, 1) == 74);
        check("no_mutation_of_original_replies", English(rows[0]) == "Buy" && English(rows[1]) == "Unavailable secret");
        testReplies = [&](uint32_t, const CExoLocString* values, uint32_t*, uint32_t, uint32_t, ObjectID, uint8_t, int, uint32_t, int) {
            check("oversize_or_overflow_uses_original_array", values == rows); return 1;
        };
        Replies(nullptr, 1, rows, indices, 1, 0xffffffff, 12, 0, 0, 0, 0);
        Replies(nullptr, 1, rows, indices, 257, 0, 12, 0, 0, 0, 0);
        testChosen = [&](uint32_t id, uint32_t index, uint32_t entry, CExoLocString value, ObjectID target, uint8_t gender, int end) {
            check("chosen_reply_recipient_and_arguments", id == 2 && index == 7 && entry == 42 && target == 12 && gender == 0 && end == 1 && English(value) == "DE Buy");
            return 75;
        };
        check("chosen_return_preserved", Chosen(nullptr, 2, 7, 42, buy, 12, 0, 1) == 75);
        int before = calls;
        check("unapproved_source_stays_native", !Translate(1, text("Secret"), "dialogue_entry", 0));
        check("source_edit_stays_native_until_registered", !Translate(1, text("Welcome changed"), "dialogue_entry", 0));
        check("markup_stays_native", !Translate(1, text("<FirstName>"), "dialogue_entry", 0));
        check("wrong_kind_stays_native", !Translate(1, buy, "dialogue_entry", 0));
        check("rejected_sources_do_not_request_translation", before == calls);
        {
            FrameScope nested(other, nullptr);
            check("nested_dialogue_does_not_use_outer_nodes", !Translate(1, welcome, "dialogue_entry", 0));
        }
        check("outer_context_restored", Translate(1, welcome, "dialogue_entry", 0).has_value());
        Delivery nested{nodes.begin()->second, 101, ""};
        {
            DeliveryScope scope(&nested);
            check("recursive_callback_leaves_original", !Translate(1, welcome, "dialogue_entry", 0));
        }
        check("delivery_context_restored", currentDelivery == nullptr);
        nodes.emplace(std::make_pair("dialogue_entry", 1), Node{"other", "dialogue_entry", "Welcome", 1, 100002, 10});
        check("ambiguous_resource_stays_native", !Translate(1, welcome, "dialogue_entry", 0));
        dialogs.erase(d);
        check("removed_context_stays_native", !Translate(1, welcome, "dialogue_entry", 0));
    }
    check("missing_frame_stays_native", !Translate(1, welcome, "dialogue_entry", 0));
    testRecipient = {}; testCallback = {}; testEntry = {}; testReplies = {}; testChosen = {};
    return report + (failures == 0 ? "RW_INV_TEST recipient_adapter_checks PASS" : "RW_INV_TEST recipient_adapter_checks FAIL");
}
