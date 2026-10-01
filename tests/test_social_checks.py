"""Server-confirmed social checks: isolation, reuse, validation and dialogue order."""

import threading
import unittest
from unittest.mock import patch
from roleweaver import social_checks
from tests import test_live_encounters as live_tests


class SocialCheckTests(unittest.TestCase):
    setUp = live_tests.LiveEncounterTests.setUp
    tearDown = live_tests.LiveEncounterTests.tearDown
    place = live_tests.LiveEncounterTests.place
    confirm = live_tests.LiveEncounterTests.confirm

    def prepare(self):
        scene = self.place()
        self.confirm(scene)
        for npc in scene["actors"]:
            self.app.states[npc]["encounter_protocol"] = 5
        key = scene["run"]["template"]["id"]
        settings = social_checks.policy()
        settings["enabled"] = True
        self.app.save_social_checks(dict(id=key, settings=settings))
        self.app.control_live(key, "start")
        return scene, next(iter(scene["actors"]))

    def resolve(self, npc, speech="Let us pass", player="player"):
        return self.app.resolve_social_check(
            npc,
            player,
            "pc",
            dict(event_id="game:1"),
            self.app.generations.get(npc, 0),
            dict(self.app.states[npc]),
            speech,
            [],
            dict(self.app.config),
        )

    def game(self, original):
        def command(npc, kind, **fields):
            request = original(npc, kind, **fields)
            if kind == "social_roll":

                def respond():
                    with self.app.lock:
                        self.app.social_result(
                            dict(
                                kind="social_result",
                                npc=npc,
                                world="test",
                                session="game",
                                epoch=1,
                                token=fields["token"],
                                request=request,
                                attempt=fields["attempt"],
                                skill=fields["skill"],
                                dc=15,
                                roll=7,
                                modifier=3,
                                total=10,
                                success=0,
                            )
                        )

                threading.Thread(target=respond, daemon=True).start()
            return request

        return command

    def test_policy_validates_fixed_dcs_and_disabled_default(self):
        self.assertFalse(social_checks.policy()["enabled"])
        for dc in (True, 0, 61, "15"):
            p = social_checks.policy()
            p["skills"]["intimidate"]["dc"] = dc
            with self.assertRaises(ValueError):
                social_checks.policy(p)

    def test_classifier_cannot_choose_dc_or_disabled_skill(self):
        settings = social_checks.policy()
        settings["skills"]["bluff"]["enabled"] = False
        for value in (
            dict(skill="intimidate", intent="pass", dc=1),
            dict(skill="bluff", intent="lie"),
            dict(skill="attack", intent="fight"),
        ):
            with (
                patch("roleweaver.social_checks.request", return_value=value),
                self.assertRaises(ValueError),
            ):
                social_checks.classify({}, {}, settings)

    def test_disabled_and_routine_speech_do_not_roll(self):
        scene, npc = self.prepare()
        scene["checks"]["enabled"] = False
        with patch("roleweaver.social_checks.classify") as classify:
            self.assertEqual(self.resolve(npc), {})
            classify.assert_not_called()
        scene["checks"]["enabled"] = True
        before = len(self.app.redis.commands)
        with patch(
            "roleweaver.social_checks.classify",
            return_value=dict(skill="none", intent=""),
        ):
            self.assertFalse(self.resolve(npc)["required"])
        self.assertEqual(len(self.app.redis.commands), before)

    def test_game_result_precedes_reply_and_rewording_reuses_roll(self):
        scene, npc = self.prepare()
        with (
            patch(
                "roleweaver.social_checks.classify",
                return_value=dict(skill="intimidate", intent="Allow passage"),
            ),
            patch.object(self.app, "command", side_effect=self.game(self.app.command)),
        ):
            result = self.resolve(npc)
            self.assertEqual(
                (result["roll"], result["modifier"], result["success"]), (7, 3, 0)
            )
            self.assertFalse(result["reused"])
            before = len(self.app.redis.commands)
            again = self.resolve(npc, "I threaten you again")
            self.assertTrue(again["reused"])
            self.assertEqual(len(self.app.redis.commands), before)
        with patch(
            "roleweaver.social_checks.classify",
            return_value=dict(skill="none", intent=""),
        ):
            result = self.resolve(npc, "What did you say?")
            self.assertEqual(result["previous_checks"][0]["success"], 0)
        self.assertEqual(len(scene["check_results"]), 1)
        self.assertEqual(next(iter(scene["check_results"].values()))["reuse_count"], 1)

    def test_pause_while_classifying_prevents_dispatch(self):
        scene, npc = self.prepare()
        before = len(self.app.redis.commands)

        def classify(*a):
            scene["run"]["status"] = "paused"
            return dict(skill="intimidate", intent="Pass")

        with (
            patch("roleweaver.social_checks.classify", side_effect=classify),
            self.assertRaises(ValueError),
        ):
            self.resolve(npc)
        self.assertEqual(len(self.app.redis.commands), before)

    def test_players_have_separate_rolls_and_scoped_director_aliases(self):
        scene, npc = self.prepare()
        with (
            patch(
                "roleweaver.social_checks.classify",
                return_value=dict(skill="persuade", intent="Pass"),
            ),
            patch.object(self.app, "command", side_effect=self.game(self.app.command)),
        ):
            self.resolve(npc, player="first-private-identity")
            self.resolve(npc, player="second-private-identity")
        self.assertEqual(len(scene["check_results"]), 2)
        context, _ = self.app.director_context(scene["run"]["template"]["id"], scene)
        rows = context["social_checks"]
        self.assertNotEqual(rows[0]["participant"], rows[1]["participant"])
        self.assertTrue(all(r["participant"].startswith("visitor-") for r in rows))
        self.assertNotIn("private-identity", str(context))
        self.assertEqual(context["social_policy"]["limits"], scene["checks"]["limits"])

    def test_cannot_change_policy_during_active_scene(self):
        scene, npc = self.prepare()
        with self.assertRaises(ValueError):
            self.app.save_social_checks(
                dict(id=scene["run"]["template"]["id"], settings=social_checks.policy())
            )

    def test_pause_while_classifying_routine_speech_also_invalidates_reply(self):
        scene, npc = self.prepare()

        def classify(*args):
            scene["run"]["status"] = "paused"
            return dict(skill="none", intent="")

        with (
            patch("roleweaver.social_checks.classify", side_effect=classify),
            self.assertRaises(ValueError),
        ):
            self.resolve(npc, "Hello")

    def test_dialogue_uses_confirmed_failure_before_choosing_action(self):
        self.draft["reaction"].update(
            attack=True,
            combat_mode="conversation",
            combat_conditions="Repeated refusal",
        )
        scene, npc = self.prepare()
        self.app.config["provider"] = "openai-compatible"
        profile = self.app.store.get(npc)
        profile["_combat_turn"] = dict(event_id="game:1", attack_ready=True)

        def reply(config, profile, memories, history):
            self.assertEqual(profile["social_check"]["success"], 0)
            self.assertEqual(profile["social_check"]["total"], 10)
            choices = [a["id"] for a in profile.get("controlled_actions", [])]
            self.assertNotIn("encounter:stand_down", choices)
            self.assertNotIn("encounter:attack", choices)
            self.assertTrue(next(iter(scene["check_results"].values()))["result"])
            return "Your threats do not impress me."

        with (
            patch(
                "roleweaver.social_checks.classify",
                return_value=dict(skill="intimidate", intent="Let me pass"),
            ),
            patch.object(self.app, "command", side_effect=self.game(self.app.command)),
            patch("roleweaver.provider.reply", side_effect=reply) as model,
        ):
            self.app.generate(
                npc,
                "player",
                profile,
                self.app.generations[npc],
                dict(self.app.states[npc]),
                "pc",
                speech="Let me pass or else",
            )
        model.assert_called_once()
        self.assertEqual(
            self.app.redis.last()["text"], "Your threats do not impress me."
        )
        self.assertFalse(self.app.redis.last()["encounter_choice"])

    def test_reused_check_allows_later_authorized_attack_without_reroll(self):
        self.draft["reaction"].update(
            attack=True,
            combat_mode="conversation",
            combat_conditions="Repeated refusal",
        )
        scene, npc = self.prepare()
        self.app.config["provider"] = "openai-compatible"
        with (
            patch(
                "roleweaver.social_checks.classify",
                return_value=dict(skill="intimidate", intent="Pass"),
            ),
            patch.object(self.app, "command", side_effect=self.game(self.app.command)),
        ):
            self.resolve(npc)
            before = len(scene["check_results"])

            def reply(config, profile, memories, history):
                self.assertTrue(profile["social_check"]["reused"])
                self.assertIn(
                    "encounter:attack", [a["id"] for a in profile["controlled_actions"]]
                )
                return '{"speech":"You were warned. Defend yourself.","action":"encounter:attack"}'

            with (
                patch(
                    "roleweaver.encounter_intent.choose",
                    return_value="encounter:attack",
                ),
                patch("roleweaver.provider.reply", side_effect=reply) as model,
            ):
                self.app.generate(
                    npc,
                    "player",
                    dict(
                        self.app.store.get(npc),
                        _combat_turn=dict(event_id="game:2", attack_ready=True),
                    ),
                    self.app.generations[npc],
                    dict(self.app.states[npc]),
                    "pc",
                    speech="Stand aside or fight",
                )
            model.assert_called_once()
        self.assertEqual(len(scene["check_results"]), before)
        self.assertEqual(self.app.redis.last()["encounter_choice"], "encounter:attack")

    def test_fresh_activation_excludes_old_resolution_but_preserves_history(self):
        scene, npc = self.prepare()
        key = scene["run"]["template"]["id"]
        self.app.store.message(npc, "player", "npc", "Old surrender")
        self.app.encounter_log(scene["run"], "Old peaceful resolution")
        self.app.encounter_observed[key] = "Old peaceful resolution"
        self.app.control_live(key, "pause")
        self.app.control_live(key, "start")
        self.app.store.message(npc, "player", "player", "New refusal")
        context, _ = self.app.director_context(key, scene)
        self.assertNotIn("Old peaceful", str(context["game_events"]))
        self.assertNotIn("Old surrender", str(context["dialogue"]))
        self.assertNotIn(key, self.app.encounter_observed)
        with (
            patch(
                "roleweaver.social_checks.classify",
                return_value=dict(skill="none", intent=""),
            ),
            patch("roleweaver.provider.reply", return_value="Then leave.") as reply,
        ):
            self.app.generate(
                npc,
                "player",
                dict(self.app.store.get(npc), _combat_turn=dict(event_id="new:1")),
                self.app.generations[npc],
                dict(self.app.states[npc]),
                "pc",
                speech="New refusal",
            )
        reply.assert_called_once()
        self.assertNotIn("Old surrender", str(reply.call_args.args[3]))
        self.assertIn("Old surrender", str(self.app.store.transcript(npc, "player")))
        for i in range(55):
            self.app.encounter_log(scene["run"], "Current event " + str(i))
        context, _ = self.app.director_context(key, scene)
        self.assertIn("Current event 54", str(context["game_events"]))

    def test_missing_confirmation_never_invents_result_or_replies_as_success(self):
        scene, npc = self.prepare()
        with (
            patch(
                "roleweaver.social_checks.classify",
                return_value=dict(skill="persuade", intent="Let me pass"),
            ),
            patch("threading.Event.wait", return_value=False),
            patch("roleweaver.provider.reply") as model,
        ):
            profile = dict(
                self.app.store.get(npc), _combat_turn=dict(event_id="game:1")
            )
            self.app.generate(
                npc,
                "player",
                profile,
                self.app.generations[npc],
                dict(self.app.states[npc]),
                "pc",
                speech="Please let me pass",
            )
        model.assert_not_called()
        self.assertIsNone(next(iter(scene["check_results"].values()))["result"])
        self.assertFalse(self.app.social_waiters)
        self.assertTrue(self.app.redis.last()["transient"])

    def test_new_game_session_during_classification_prevents_roll(self):
        scene, npc = self.prepare()
        before = len(self.app.redis.commands)

        def classify(*args):
            self.app.states[npc]["session"] = "new-game"
            return dict(skill="bluff", intent="Let me pass")

        with (
            patch("roleweaver.social_checks.classify", side_effect=classify),
            self.assertRaises(ValueError),
        ):
            self.resolve(npc)
        self.assertEqual(len(self.app.redis.commands), before)

    def test_invalid_or_stale_result_cannot_wake_waiter(self):
        scene, npc = self.prepare()
        wake = threading.Event()
        token = str(scene["run"]["started"])
        scene["check_results"] = {
            "attempt": dict(skill="intimidate", dc=15, result=None)
        }
        self.app.social_waiters["attempt"] = dict(
            event=wake,
            npc=npc,
            key=scene["run"]["template"]["id"],
            token=token,
            session="game",
            epoch=1,
            request="r",
        )
        event = dict(
            attempt="attempt",
            npc=npc,
            world="test",
            session="game",
            epoch=1,
            token=token,
            request="r",
            skill="intimidate",
            dc=15,
            roll=7,
            modifier=3,
            total=10,
            success=0,
        )
        for change in (
            dict(token="old"),
            dict(roll=25),
            dict(success=1),
            dict(total=999),
            dict(dc=1),
            dict(request="other"),
        ):
            self.app.social_result(dict(event, **change))
            self.assertFalse(wake.is_set())
        self.app.social_result(event)
        self.assertTrue(wake.is_set())
