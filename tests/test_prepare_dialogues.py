"""Offline preparation must preserve gameplay and never seed translation jobs."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.gff import read, write
from tools.build_translation_demo import build
from tools.prepare_dialogues import prepare_dialogue, prepare

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    source = json.loads((ROOT / "examples/translation_dialogue.json").read_text())
    signature, root = read(build(source, prepared=False)[0])
    fields = root[1]
    link = fields["StartingList"][1][0][1]
    link["Active"] = (11, b"quest_gate")
    link["ConditionParams"] = (
        15,
        [(0, {"Key": (10, b"permission"), "Value": (10, b"allowed")})],
    )
    node = fields["EntryList"][1][0][1]
    node["Script"] = (11, b"quest_action")
    node["ActionParams"] = (
        15,
        [(0, {"Key": (10, b"quest"), "Value": (10, b"investigation")})],
    )
    node["Quest"], node["QuestEntry"] = (10, b"investigation"), (4, 3)
    node["RepliesList"][1][0][1]["Active"] = (11, b"hidden_reply")
    return write(signature, root)


def remove_wrapper_fields(root):
    root = copy.deepcopy(root)
    fields = root[1]
    for key in ("RWTrVersion", "RWTrTokenBase", "RWTrTokenCount"):
        fields.pop(key, None)
    links = fields["StartingList"][1][:]
    for kind, link_field in (
        ("EntryList", "RepliesList"),
        ("ReplyList", "EntriesList"),
    ):
        for _, node in fields[kind][1]:
            links.extend(node[link_field][1])
    for _, link in links:
        link.pop("Active", None)
    return root


class PreparationTests(unittest.TestCase):
    def test_preserves_graph_actions_quests_text_and_parameter_data(self):
        original = fixture()
        result, wrappers, report = prepare_dialogue("test_dialog", original)
        self.assertEqual(
            remove_wrapper_fields(read(original)[1]),
            remove_wrapper_fields(read(result)[1]),
        )
        fields = read(result)[1][1]
        links = fields["StartingList"][1]
        wrapper = wrappers[links[0][1]["Active"][1].decode()]
        self.assertIn(
            'SetScriptParam("permission", GetScriptParam("permission"));', wrapper
        )
        self.assertLess(
            wrapper.index('ExecuteScript("quest_gate"'),
            wrapper.index("RWTrNodeVisible("),
        )
        self.assertIn("if (!allowed) return allowed;", wrapper)
        self.assertEqual(report["nodes"], 21)
        self.assertTrue(all(len(name) <= 16 for name in wrappers))
        self.assertEqual(original, fixture())

    def test_offline_bundle_keeps_original_and_does_not_contact_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "world"
            directory.mkdir()
            original = fixture()
            (directory / "test_dialog.dlg").write_bytes(original)
            output = Path(folder) / "review"
            with patch(
                "roleweaver.provider.complete",
                side_effect=AssertionError("Preparation must be offline"),
                create=True,
            ):
                result = prepare(None, [directory], output)
            self.assertEqual((directory / "test_dialog.dlg").read_bytes(), original)
            self.assertEqual(
                (output / "originals/test_dialog.dlg").read_bytes(), original
            )
            self.assertEqual(result["llm_requests"], 0)
            self.assertFalse(result["translation_database_written"])
            self.assertFalse(list(Path(folder).rglob("*.sqlite*")))
            self.assertFalse(result["compiled"])
            self.assertTrue(list((output / "scripts").glob("rtd_*.nss")))
            with self.assertRaises(ValueError):
                prepare(None, [directory], output)

    def test_collision_and_repreparation_cannot_silently_change_world(self):
        original = fixture()
        prepared = prepare_dialogue("test_dialog", original)[0]
        with self.assertRaisesRegex(ValueError, "Already prepared"):
            prepare_dialogue("test_dialog", prepared)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "world"
            directory.mkdir()
            (directory / "test_dialog.dlg").write_bytes(original)
            (directory / "other.nss").write_text(
                'void main(){SetCustomToken(3000000,"existing");}'
            )
            output = Path(folder) / "review"
            with self.assertRaisesRegex(ValueError, "collides"):
                prepare(None, [directory], output)
            self.assertFalse(output.exists())

    def test_existing_prepared_example_is_reported_and_not_double_wrapped(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "world"
            directory.mkdir()
            (directory / "test_dialog.dlg").write_bytes(fixture())
            (directory / "rw_tr_demo.dlg").write_bytes(
                (ROOT / "assets/rw_tr_demo.dlg").read_bytes()
            )
            result = prepare(None, [directory], Path(folder) / "review")
            self.assertEqual(
                [r["resource"] for r in result["dialogues"]], ["test_dialog"]
            )
            self.assertEqual(result["skipped"][0]["resource"], "rw_tr_demo")


if __name__ == "__main__":
    unittest.main()
