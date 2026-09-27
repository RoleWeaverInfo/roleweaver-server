"""Observation boundaries and current-world grounding without real LLM calls."""

import json
import unittest
from unittest.mock import patch
from roleweaver import perception, provider
from roleweaver.store import DEFAULT_NPC


class PerceptionTests(unittest.TestCase):
    def test_player_identity_and_hidden_properties_never_survive(self):
        rows = perception.observations(
            [
                dict(
                    kind="character",
                    player=1,
                    label="Secret PC Name",
                    distance=2.34,
                    bearing="left",
                    condition="injured",
                    activity="fighting",
                    merchant=1,
                    inventory=["secret key"],
                    object="7ffff123",
                    account="private",
                ),
                dict(
                    kind="container",
                    label="Chest",
                    distance=4.0,
                    open="closed",
                    usable=1,
                    locked=True,
                    trap="poison",
                    contents="gold",
                    quest="hidden",
                ),
                dict(kind="character", label="DM", distance=1, dm=True),
                dict(
                    kind="character", label="Possessed NPC", distance=1, possessed=True
                ),
            ]
        )
        self.assertEqual(
            rows[0],
            dict(
                kind="character",
                player=True,
                label="Unidentified traveler",
                distance=2.3,
                bearing="left",
                condition="injured",
                activity="fighting",
            ),
        )
        self.assertEqual(
            rows[1],
            dict(
                kind="container",
                label="Chest",
                distance=4.0,
                open="closed",
                usable=True,
            ),
        )
        self.assertEqual(len(rows), 2)

    def test_malformed_fields_and_scan_limit(self):
        self.assertEqual(perception.observations("bad"), [])
        self.assertEqual(
            perception.observations(
                [
                    None,
                    dict(kind=[], distance=2),
                    dict(kind="door", distance=float("nan")),
                    dict(kind="door", distance=True),
                    dict(kind="door", distance=13),
                ]
            ),
            [],
        )
        row = dict(
            kind="door",
            label="<script>not html</script>",
            distance=5,
            bearing=[],
            open={},
            usable=2,
        )
        clean = perception.observations([row] * 30)
        self.assertEqual(len(clean), 24)
        self.assertEqual(set(clean[0]), {"kind", "label", "distance"})

    def test_stale_connection_or_cached_scan_is_not_current_knowledge(self):
        state = dict(
            seen=100,
            tick=20,
            perception_tick=19,
            perception_protocol=2,
            area="Hall",
            surroundings=[dict(kind="door", label="Gate", distance=4, open="open")],
        )
        self.assertTrue(perception.snapshot(state, now=101)["available"])
        self.assertFalse(perception.snapshot(state, now=105)["available"])
        self.assertFalse(
            perception.snapshot(dict(state, perception_tick=10), now=101)["available"]
        )
        self.assertFalse(
            perception.snapshot(dict(state, perception_tick=30), now=101)["available"]
        )
        self.assertEqual(perception.snapshot(state, now=105)["objects"], [])

    def test_area_wide_distances_and_limits_require_new_protocol(self):
        row = dict(kind="character", player=1, label="SecretName", distance=85.0)
        state = dict(
            seen=100,
            tick=10,
            perception_tick=10,
            perception_protocol=3,
            surroundings=[row] * 300,
            perception_truncated=1,
        )
        result = perception.snapshot(state, now=101)
        self.assertTrue(result["available"])
        self.assertIsNone(result["radius_metres"])
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["objects"]), 256)
        self.assertEqual(result["objects"][0]["distance"], 85.0)
        self.assertNotIn("SecretName", str(result))
        self.assertEqual(
            perception.snapshot(dict(state, perception_protocol=2), now=101)["objects"],
            [],
        )
        self.assertFalse(
            perception.snapshot(dict(state, perception_tick=1), now=101)["available"]
        )

    def test_basic_bridge_remains_supported(self):
        result = perception.snapshot(
            dict(
                seen=100,
                surroundings=[dict(kind="placeable", label="Table", distance=1)],
            ),
            now=101,
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["detail"], "basic")
        self.assertEqual(result["objects"][0]["label"], "Table")

    def test_prompt_uses_filtered_snapshot_and_explains_limits(self):
        snapshot = perception.snapshot(
            dict(
                seen=100,
                area="Hall",
                self_condition="injured",
                surroundings=[
                    dict(kind="character", player=1, label="PrivateName", distance=2)
                ],
            ),
            now=101,
        )
        with patch.object(provider, "complete", return_value="Hello") as complete:
            provider.reply(
                dict(
                    provider="openai-compatible",
                    base_url="https://example.invalid/v1",
                    model="test",
                ),
                dict(DEFAULT_NPC, perception=snapshot),
                [],
                [],
            )
        payload = json.loads(complete.call_args.args[1])
        system = payload["messages"][0]["content"]
        self.assertNotIn("PrivateName", system)
        self.assertIn("Unidentified traveler", system)
        self.assertIn("not permission", system)
        self.assertIn("Container contents remain unknown unless", system)
        self.assertIn(
            "Locks, traps and destinations behind doors remain unknown", system
        )


if __name__ == "__main__":
    unittest.main()
