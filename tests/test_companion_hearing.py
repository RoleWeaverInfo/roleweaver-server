"""Public speech is context, not authority, persistent history or extra model work."""

import json
import unittest
from unittest.mock import patch

from roleweaver import companion_hearing, companion_preferences, perception, provider
from tests import test_companions


class HearingTests(unittest.TestCase):
    def event(self, **changes):
        return dict(
            dict(
                seen=100,
                tick=200,
                hearing_protocol=1,
                hearing_enabled=1,
                companion_preferences_protocol=2,
                companion_preferences=dict(companion_preferences.DEFAULT, listening=1),
                heard_speech=[
                    dict(
                        channel="talk",
                        tick=198,
                        speaker_kind="npc",
                        speaker="Grust",
                        appearance="Troll",
                        text="Pay for her freedom.",
                    )
                ],
            ),
            **changes,
        )

    def test_opt_in_service_policy_and_freshness_required(self):
        e = self.event()
        self.assertEqual(
            companion_hearing.context(e, {}, now=101)["lines"][0]["speaker"], "Grust"
        )
        self.assertEqual(
            companion_hearing.context(
                e, {"companion_listening_enabled": False}, now=101
            )["lines"],
            [],
        )
        for change in (
            dict(companion_preferences=companion_preferences.DEFAULT),
            dict(companion_preferences_protocol=1),
            dict(hearing_protocol=0),
            dict(hearing_enabled=0),
            dict(seen=95),
            dict(seen=102),
            dict(tick="200"),
            dict(heard_speech=None),
        ):
            with self.subTest(change=change):
                self.assertEqual(
                    companion_hearing.context(dict(e, **change), {}, now=101)["lines"],
                    [],
                )

    def test_invalid_channels_age_commands_and_hidden_data_are_dropped(self):
        row = self.event()["heard_speech"][0]
        bad = [
            dict(row, **change)
            for change in (
                dict(channel="tell"),
                dict(channel="party"),
                dict(channel="whisper"),
                dict(tick=79),
                dict(tick=201),
                dict(tick=True),
                dict(text="x" * 401),
                dict(text=" /rw companion follow me"),
                dict(text="(( OOC"),
                dict(speaker_kind="dm"),
                dict(text=None),
            )
        ]
        for item in bad:
            self.assertEqual(
                companion_hearing.context(self.event(heard_speech=[item]), {}, now=101)[
                    "lines"
                ],
                [],
            )
        player = dict(
            row,
            speaker_kind="player",
            speaker="Secret name",
            owner_key="private",
            object="private",
            text="I can help.",
        )
        clean = companion_hearing.context(
            self.event(heard_speech=[player]), {}, now=101
        )
        self.assertNotIn("Secret name", str(clean))
        self.assertNotIn("private", str(clean))
        self.assertEqual(clean["lines"][0]["speaker"], "Unidentified traveler")
        self.assertEqual(
            len(
                companion_hearing.context(
                    self.event(heard_speech=[row] * 40), {}, now=101
                )["lines"]
            ),
            8,
        )

    def test_creature_descriptions_are_bounded_and_player_names_not_inferred(self):
        rows = perception.observations(
            [
                dict(
                    kind="character",
                    label="Grust",
                    distance=2,
                    appearance="Troll",
                    description="A hulking figure.",
                    secret="kidnapper",
                ),
                dict(
                    kind="character",
                    player=1,
                    label="Private name",
                    distance=3,
                    appearance="Human",
                    description="Private name is my name.",
                ),
            ]
        )
        self.assertEqual(rows[0]["appearance"], "Troll")
        self.assertEqual(rows[0]["description"], "A hulking figure.")
        self.assertNotIn("secret", rows[0])
        self.assertNotIn("description", rows[1])
        self.assertNotIn("Private name", str(rows))
        many = perception.observations(
            [dict(kind="character", label="Actor", distance=1, description="x" * 1000)]
            * 256,
            area_wide=True,
        )
        self.assertEqual(sum(len(r.get("description", "")) for r in many), 12 * 240)


class HearingServiceTests(unittest.TestCase):
    setUp = test_companions.CompanionTests.setUp
    tearDown = test_companions.CompanionTests.tearDown
    event = test_companions.CompanionTests.event
    run_chat = test_companions.CompanionTests.run_chat

    def heard_event(self, **changes):
        fields = HearingTests().event()
        fields.pop("seen")
        return self.event(**dict(fields, **changes))

    def test_hearing_alone_does_not_request_model_or_write_history(self):
        self.app.config["companions_enabled"] = True
        before = self.app.store.list_npcs()
        with patch.object(self.app.pool, "submit") as submit:
            self.app.event(self.heard_event(kind="companion_state"))
        self.assertFalse(submit.called)
        self.assertEqual(self.app.store.list_npcs(), before)

    def test_speech_is_transient_scrubbed_context_and_cannot_add_permissions(self):
        def inspect(config, profile, memories, history):
            self.assertEqual(profile["heard_speech"]["lines"][0]["appearance"], "Troll")
            self.assertEqual(
                profile["heard_speech"]["lines"][0]["text"], "Pay for her freedom."
            )
            self.assertNotIn("Pay for her freedom", json.dumps([history, memories]))
            self.assertEqual(
                {r["id"] for r in profile["controlled_actions"]},
                {"companion:follow", "companion:stay"},
            )
            with patch.object(
                provider,
                "complete",
                return_value='{"speech":"I heard the demand.","action":""}',
            ) as complete:
                provider.reply(
                    dict(config, base_url="https://example.invalid/v1", model="test"),
                    profile,
                    memories,
                    history,
                )
                system = str(complete.call_args)
                self.assertIn("untrusted testimony", system)
                self.assertIn("current direct request", system)
                self.assertIn("Pay for her freedom", system)
            return '{"speech":"I heard the demand.","action":""}'

        npc = self.run_chat(self.heard_event(), effect=inspect)
        self.assertNotIn("heard_speech", self.app.store.get(npc))
        self.assertNotIn(
            "Pay for her freedom", json.dumps(self.app.store.transcript(npc, npc))
        )
        self.assertNotIn("Pay for her freedom", json.dumps(self.app.backup_data()))

    def test_review_delay_does_not_expire_context_mid_reply(self):
        self.app.config.update(companions_enabled=True, provider="openai-compatible")
        with patch.object(self.app.pool, "submit") as submit:
            self.app.event(self.heard_event())
        fn, npc, event, profile, config = submit.call_args.args

        def review(*args):
            event["seen"] -= 10
            return "allow"

        def reply(config, profile, *args):
            self.assertTrue(profile["heard_speech"]["lines"])
            return '{"speech":"I heard Grust.","action":""}'

        with (
            patch.object(self.app, "review_dialogue", side_effect=review),
            patch("roleweaver.companions.provider.reply", side_effect=reply),
        ):
            fn(npc, event, profile, config)
