"""Private display routing, cache invalidation, and the authored dialogue graph."""

import copy
import json
import struct
import tempfile
import threading
import unittest
from pathlib import Path

from roleweaver.translation import TranslationCache, DEFAULT
from roleweaver.translation_service import TranslationService
from roleweaver.translation_surfaces import lookup_batch
from tests.test_actions import FakeRedis
from tools.build_translation_demo import build, build_creature
from tools.add_translation_guide import add_guide
from tools.module_copy import resources
from tools.gff import read, write

ROOT = Path(__file__).resolve().parents[1]


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = TranslationCache(Path(self.tmp.name) / "cache.sqlite3")
        self.cache.configure(dict(DEFAULT, enabled=True, per_minute=60))
        self.pref = dict(enabled=True, language="fr")
        self.dialogue = dict(
            kind="translation_dialogue",
            session="session",
            dialogue="rw_tr_demo",
            texts=[
                dict(id=0, kind="dialogue_entry", approved=1, text="Welcome."),
                dict(
                    id=1,
                    kind="dialogue_reply",
                    approved=1,
                    text="Where can I buy supplies?",
                ),
            ],
        )
        self.names = dict(
            kind="translation_names",
            session="session",
            texts=[
                dict(
                    object="00000001",
                    object_type=64,
                    player_character=0,
                    resref="chest",
                    name_mode="auto",
                    approved=1,
                    text="Chest",
                )
            ],
        )

    def tearDown(self):
        self.cache.db.close()
        self.tmp.cleanup()

    def lookup(self, payload, pref=None, active=True):
        return lookup_batch(self.cache, payload, pref or self.pref, active)

    def finish(self):
        while self.cache.jobs:
            self.assertTrue(self.cache.process_one(lambda row: "FR " + row["original"]))

    def test_dialogue_reuses_nodes_and_invalidates_only_changed_line(self):
        first = self.lookup(self.dialogue)
        self.assertTrue(all(not row["translated"] for row in first))
        self.finish()
        # A different player/session sees the same cached authored text.
        second = self.lookup(dict(self.dialogue, session="other"))
        self.assertEqual(
            [r["translated"] for r in second],
            ["FR " + r["text"] for r in self.dialogue["texts"]],
        )
        changed = copy.deepcopy(self.dialogue)
        changed["texts"][0]["text"] = "Good evening."
        rows = self.lookup(changed)
        self.assertEqual(rows[0]["translated"], "")
        self.assertEqual(rows[1]["translated"], second[1]["translated"])
        self.assertEqual(len(self.cache.jobs), 1)
        self.assertEqual(
            [{k: v for k, v in r.items() if k != "translated"} for r in rows],
            changed["texts"],
        )

    def test_disabled_and_other_language_do_not_leak_cached_translation(self):
        self.lookup(self.dialogue)
        self.finish()
        off = self.lookup(self.dialogue, active=False)
        self.assertTrue(all(not r["translated"] for r in off))
        self.assertFalse(self.cache.jobs)
        other = self.lookup(self.dialogue, dict(enabled=True, language="es"))
        self.assertTrue(all(not r["translated"] for r in other))
        self.assertEqual(len(self.cache.jobs), 2)

    def test_validate_whole_batch_before_queueing_any_text(self):
        for replacement in [
            dict(id=1, kind="chat", approved=1, text="No chat"),
            dict(id=1, kind="dialogue_reply", approved=0, text="No"),
            dict(id=0, kind="dialogue_entry", approved=1, text="Duplicate"),
        ]:
            bad = copy.deepcopy(self.dialogue)
            bad["texts"][1] = replacement
            with self.assertRaises(ValueError):
                self.lookup(bad)
            self.assertFalse(self.cache.jobs)
        with self.assertRaises(ValueError):
            self.lookup(dict(self.dialogue, dialogue=None))

    def test_player_and_unsupported_hover_types_never_queue(self):
        for update in [
            dict(player_character=1),
            dict(object_type=8),
            dict(object_type=16),
            dict(name_mode="unknown"),
            dict(object="invalid"),
        ]:
            bad = copy.deepcopy(self.names)
            bad["texts"][0].update(update)
            with self.assertRaises(ValueError):
                self.lookup(bad)
            self.assertFalse(self.cache.jobs)

    def test_native_object_ids_accept_short_hex_and_reject_invalid_or_duplicate_ids(
        self,
    ):
        original = self.names["texts"][0]
        for object_id in ("3", "e", "21", "0000003A"):
            rows = self.lookup(
                dict(self.names, texts=[dict(original, object=object_id)])
            )
            self.assertEqual(rows[0]["object"], object_id)
        self.assertEqual(len(self.cache.jobs), 1)  # Same visible label, one job.
        self.finish()
        for object_id in ("", "x", "3;drop", "123456789", "7f000000", "-1"):
            with self.subTest(object_id=object_id), self.assertRaises(ValueError):
                self.lookup(dict(self.names, texts=[dict(original, object=object_id)]))
        with self.assertRaises(ValueError):
            self.lookup(
                dict(
                    self.names,
                    texts=[
                        dict(original, object="e"),
                        dict(original, object="0000000E"),
                    ],
                )
            )
        self.assertFalse(self.cache.jobs)

    def test_native_hover_event_reaches_private_reply_through_service_dispatch(self):
        from roleweaver.service import Service

        app = TranslationService()
        app.lock, app.directory, app.salt = (
            threading.RLock(),
            Path(self.tmp.name),
            "test",
        )
        app.config, app.world_session = dict(world_id="world"), "session"
        app._translations, app.redis, app.prefix = self.cache, FakeRedis(), "test"
        base = dict(
            world="world",
            session="session",
            identity="private-key",
            player="2a",
            token="player-token",
            seq=7,
            tick=100,
        )
        Service.event(
            app, dict(base, kind="translation_preference", enabled=1, language="fr")
        )
        original = self.names["texts"][0]
        payload = dict(
            base,
            kind="translation_names",
            texts=[
                dict(original, object="3"),
                dict(
                    original,
                    object="e",
                    object_type=1,
                    resref="rw_base",
                    text="Merchant",
                ),
                dict(
                    original,
                    object="21",
                    object_type=1,
                    text="Beran",
                    name_mode="preserve",
                ),
            ],
        )
        Service.event(app, payload)
        self.assertEqual(app.redis.last()["kind"], "translation_names_reply")
        self.assertEqual(len(self.cache.jobs), 2)
        self.finish()
        Service.event(app, payload)
        reply = app.redis.last()
        self.assertEqual(
            [r["translated"] for r in reply["texts"]], ["FR Chest", "FR Merchant", ""]
        )
        self.assertEqual(
            (reply["player"], reply["token"], reply["seq"]), ("2a", "player-token", 7)
        )
        self.assertNotIn("identity", reply)
        # An observer with no language preference never receives these overrides.
        Service.event(
            app, dict(payload, player="2b", identity="other-key", token="other-token")
        )
        self.assertEqual(app.redis.last()["enabled"], 0)
        self.assertTrue(all(not r["translated"] for r in app.redis.last()["texts"]))

    def test_preserve_and_translate_policies_and_examine_cache_sharing(self):
        original = self.names["texts"][0]
        self.lookup(dict(self.names, texts=[dict(original, name_mode="preserve")]))
        self.assertFalse(self.cache.jobs)
        self.lookup(self.names)
        self.finish()
        self.assertEqual(
            self.cache.lookup("examined:name", "fr", "name", "Chest", "chest:64"),
            "FR Chest",
        )
        self.assertEqual(
            self.lookup(dict(self.names, texts=[dict(original, name_mode="preserve")]))[
                0
            ]["translated"],
            "",
        )
        forced = self.lookup(
            dict(self.names, texts=[dict(original, name_mode="translate")])
        )
        self.assertEqual(forced[0]["translated"], "")
        self.assertEqual(len(self.cache.jobs), 1)
        renamed = self.lookup(
            dict(self.names, texts=[dict(original, text="New chest")])
        )
        self.assertEqual(renamed[0]["translated"], "")

    def test_service_routes_private_batch_with_session_and_no_identity(self):
        app = TranslationService()
        app.lock, app.directory, app.salt = (
            threading.RLock(),
            Path(self.tmp.name),
            "test",
        )
        app.config, app.world_session = dict(world_id="world"), "session"
        app._translations, app.redis, app.prefix = self.cache, FakeRedis(), "test"
        base = dict(
            world="world",
            session="session",
            identity="private-key",
            player="00000005",
            token="player-token",
            seq=7,
            tick=100,
        )
        app.translation_event(
            dict(base, kind="translation_preference", enabled=1, language="fr")
        )
        payload = dict(
            base,
            **{k: v for k, v in self.dialogue.items() if k != "session"},
            speaker="00000009",
        )
        app.translation_event(payload)
        reply = app.redis.last()
        self.assertEqual(reply["kind"], "translation_dialogue_reply")
        self.assertEqual(
            (
                reply["player"],
                reply["token"],
                reply["speaker"],
                reply["seq"],
                reply["expires"],
            ),
            ("00000005", "player-token", "00000009", 7, 105),
        )
        self.assertNotIn("identity", reply)
        self.finish()
        app.translation_event(payload)
        self.assertTrue(all(r["translated"] for r in app.redis.last()["texts"]))
        # A second player has translation disabled by default and cannot inherit it.
        app.translation_event(
            dict(payload, player="00000006", identity="other-key", token="other-token")
        )
        self.assertEqual(app.redis.last()["enabled"], 0)
        self.assertTrue(all(not r["translated"] for r in app.redis.last()["texts"]))

    def test_on_demand_delivery_only_caches_reached_node_and_rejects_stale_source(self):
        app = TranslationService()
        app.lock, app.directory, app.salt = (
            threading.RLock(),
            Path(self.tmp.name),
            "test",
        )
        app.config, app.world_session = dict(world_id="world"), "session"
        app._translations, app.redis, app.prefix = self.cache, FakeRedis(), "test"
        base = dict(
            world="world",
            session="session",
            identity="private-key",
            player="00000005",
            token="session-token",
            seq=1,
            tick=100,
        )
        app.translation_event(
            dict(base, kind="translation_preference", enabled=1, language="fr")
        )
        row = dict(
            id=500,
            kind="dialogue_entry",
            approved=1,
            text="Visible quest question.",
            display_token=3000500,
        )
        payload = dict(
            base,
            kind="translation_dialogue",
            dialogue="quest",
            speaker="00000009",
            on_demand=1,
            texts=[row],
        )
        app.translation_event(payload)
        self.assertEqual(len(self.cache.jobs), 1)
        self.assertEqual(len(app._translation_waiting), 1)
        self.assertEqual(self.cache.status()["pending"], 1)
        self.finish()
        app.translation_deliver_ready()
        self.assertEqual(
            app.redis.last()["texts"][0]["translated"], "FR Visible quest question."
        )
        self.assertEqual(app.redis.last()["on_demand"], 1)
        self.assertFalse(app._translation_waiting)
        # A newer source cancels the old result; draining never rewrites its source mapping.
        app.translation_event(
            dict(payload, seq=2, texts=[dict(row, text="Old revised question.")])
        )
        app.translation_event(
            dict(payload, seq=3, texts=[dict(row, text="New revised question.")])
        )
        self.finish()
        app.translation_deliver_ready()
        self.assertEqual(app.redis.last()["seq"], 3)
        self.assertEqual(
            app.redis.last()["texts"][0]["translated"], "FR New revised question."
        )
        originals = [
            r[0] for r in self.cache.db.execute("SELECT original FROM entries")
        ]
        self.assertNotIn("Unvisited secret branch.", originals)
        self.assertEqual(len(originals), 3)

    def test_same_entry_and_reply_index_have_separate_sources(self):
        payload = dict(
            self.dialogue,
            texts=[
                dict(id=0, kind="dialogue_entry", approved=1, text="Question"),
                dict(id=0, kind="dialogue_reply", approved=1, text="Answer"),
            ],
        )
        self.lookup(payload)
        self.finish()
        self.assertEqual(
            [r["translated"] for r in self.lookup(payload)],
            ["FR Question", "FR Answer"],
        )

    def test_three_actual_recipients_have_independent_languages_and_subscriptions(self):
        app = TranslationService()
        app.lock, app.directory, app.salt = (
            threading.RLock(),
            Path(self.tmp.name),
            "test",
        )
        app.config, app.world_session = dict(world_id="world"), "session"
        app._translations, app.redis, app.prefix = self.cache, FakeRedis(), "test"
        recipients = [
            dict(
                world="world",
                session="session",
                player=str(i),
                identity=f"key-{i}",
                token=f"login-{i}",
                seq=1,
                tick=100,
            )
            for i in (1, 2, 3)
        ]
        for base, language in zip(recipients[:2], ("fr", "de")):
            app.translation_event(
                dict(base, kind="translation_preference", enabled=1, language=language)
            )

        def deliver(base, text="Welcome."):
            app.translation_event(
                dict(
                    base,
                    kind="translation_dialogue",
                    on_demand=1,
                    dialogue="quest",
                    speaker="a",
                    texts=[
                        dict(
                            id=0,
                            kind="dialogue_entry",
                            approved=1,
                            text=text,
                            display_token=3000000,
                        )
                    ],
                )
            )

        for base in recipients:
            deliver(base)
        self.assertEqual(len(self.cache.jobs), 2)  # Two languages; third viewer is off.
        self.assertEqual(len(app._translation_waiting), 2)
        while self.cache.jobs:
            self.cache.process_one(lambda row: row["target"] + ": " + row["original"])
        app.redis.commands.clear()
        app.translation_deliver_ready()
        replies = [json.loads(c[-1]) for c in app.redis.commands if c[0] == "RPUSH"]
        self.assertEqual(
            {r["player"]: r["texts"][0]["translated"] for r in replies},
            {"1": "fr: Welcome.", "2": "de: Welcome."},
        )
        self.assertEqual({r["token"] for r in replies}, {"login-1", "login-2"})
        self.assertFalse(app._translation_waiting)
        # Source edits are independent of player cache preferences. If one turns
        # off while pending, only the other viewer receives the new translation.
        for base in recipients[:2]:
            deliver(dict(base, seq=2), "Revised welcome.")
        app.translation_event(
            dict(recipients[0], kind="translation_preference", enabled=0, language="fr")
        )
        while self.cache.jobs:
            self.cache.process_one(lambda row: row["target"] + ": " + row["original"])
        app.redis.commands.clear()
        app.translation_deliver_ready()
        replies = [json.loads(c[-1]) for c in app.redis.commands if c[0] == "RPUSH"]
        self.assertEqual(
            [(r["player"], r["seq"], r["texts"][0]["translated"]) for r in replies],
            [("2", 2, "de: Revised welcome.")],
        )
        # A restarted world cannot receive a late result from its previous session.
        deliver(dict(recipients[1], seq=3), "New scene.")
        app.world_session = "restarted"
        self.finish()
        app.redis.commands.clear()
        app.translation_deliver_ready()
        self.assertFalse(app.redis.commands)
        self.assertFalse(app._translation_waiting)


class DialogueAssetTests(unittest.TestCase):
    def test_ordinary_guide_and_module_patch_preserve_existing_content(self):
        blueprint = build_creature((ROOT / "assets/rw_base.utc").read_bytes())
        self.assertEqual(blueprint, (ROOT / "assets/rw_tr_guide.utc").read_bytes())
        fields = read(blueprint)[1][1]
        self.assertEqual(fields["Conversation"], (11, b"rw_tr_demo"))
        self.assertEqual(fields["ScriptDialogue"], (11, b"rw_tr_talk"))
        self.assertEqual(fields["VarTable"], (15, []))
        self.assertFalse(fields["ScriptHeartbeat"][1])
        mod = write(
            b"IFO V3.2",
            (
                0,
                dict(
                    Mod_Entry_Area=(11, b"hall"),
                    Mod_Entry_X=(8, 25.0),
                    Mod_Entry_Y=(8, 19.0),
                    Mod_Entry_Z=(8, 0.0),
                ),
            ),
        )
        original_npc = (
            4,
            dict(Tag=(10, b"existing"), Conversation=(11, b"original_dialog")),
        )
        git = write(
            b"GIT V3.2",
            (
                0,
                {
                    "Creature List": (15, [original_npc]),
                    "Placeable List": (15, [(9, {"Tag": (10, b"do_not_change")})]),
                },
            ),
        )
        original = [
            ("module", 2014, mod),
            ("hall", 2023, git),
            ("unrelated", 10, b"preserve me"),
        ]
        header = bytearray(b"MOD V1.0" + b"\0" * 152)
        ko, ro, offset = 160, 160 + 24 * len(original), 160 + 32 * len(original)
        struct.pack_into("<4I", header, 16, len(original), 160, ko, ro)
        keys, indices, data = bytearray(), bytearray(), bytearray()
        for i, (name, kind, value) in enumerate(original):
            keys.extend(struct.pack("<16sIHH", name.encode(), i, kind, 0))
            indices.extend(struct.pack("<II", offset + len(data), len(value)))
            data.extend(value)
        raw = bytes(header + keys + indices + data)
        dialogue = (ROOT / "assets/rw_tr_demo.dlg").read_bytes()
        patched = add_guide(raw, blueprint, dialogue)
        self.assertEqual(patched, add_guide(patched, blueprint, dialogue))
        entries = {(n, k): d for n, k, d in resources(patched)}
        self.assertEqual(entries["module", 2014], mod)
        self.assertEqual(entries["unrelated", 10], b"preserve me")
        area = read(entries["hall", 2023])[1][1]
        self.assertEqual(area["Creature List"][1][0], original_npc)
        self.assertEqual(area["Placeable List"], read(git)[1][1]["Placeable List"])
        guide = area["Creature List"][1][1][1]
        self.assertEqual(guide["XPosition"], (8, 28.0))
        self.assertEqual(guide["YPosition"], (8, 21.0))
        self.assertEqual(guide["Conversation"], (11, b"rw_tr_demo"))
        self.assertEqual(entries["rw_tr_demo", 2029], dialogue)

    def test_generated_asset_and_manifest_match_editable_source_and_branch_graph(self):
        source = json.loads((ROOT / "examples/translation_dialogue.json").read_text())
        dlg, script = build(source)
        self.assertEqual(dlg, (ROOT / "assets/rw_tr_demo.dlg").read_bytes())
        self.assertEqual(script, (ROOT / "bridge/rw_tr_demo.nss").read_text())
        signature, root = read(dlg)
        self.assertEqual(signature, b"DLG V3.2")
        fields = root[1]
        entries, replies = fields["EntryList"][1], fields["ReplyList"][1]
        self.assertEqual((len(entries), len(replies)), (4, 5))
        tokens = []
        for node in entries + replies:
            tokens.append(node[1]["Text"][1])
            self.assertEqual(node[1]["Delay"], (4, 0xFFFFFFFF))
            self.assertTrue(
                node[1]["Comment"][1]
            )  # English remains available to a builder.
        self.assertEqual(len(set(tokens)), 9)
        root_links = [n[1]["Index"][1] for n in entries[0][1]["RepliesList"][1]]
        self.assertEqual(root_links, [0, 1, 2, 3])
        for i in range(3):
            self.assertEqual(replies[i][1]["EntriesList"][1][0][1]["Index"][1], i + 1)
        self.assertEqual(replies[3][1]["EntriesList"][1], [])  # Goodbye terminates.
        self.assertEqual(
            replies[4][1]["EntriesList"][1][0][1]["Index"][1], 0
        )  # Return.
        self.assertEqual(fields["EndConversation"][1], b"rw_tr_end")
        self.assertEqual(fields["EndConverAbort"][1], b"rw_tr_end")
