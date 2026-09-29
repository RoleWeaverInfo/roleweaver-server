"""Build isolated engine-test assets. Never install these in a live world.

Call build_fixture(output) before compiling dialogue_preparation_native.nss as
the isolated module's OnModuleLoad. Requires NWNX Dialog, Util, Player and the
normal bridge headers. No provider or Redis connection is needed.
"""

import json
from pathlib import Path

from demo.investigation.gff_tools import read, write
from tools.build_translation_demo import build
from tools.prepare_dialogues import prepare_dialogue

ROOT = Path(__file__).resolve().parents[1]


def build_fixture(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    raw, _ = build(
        json.loads((ROOT / "examples/translation_dialogue.json").read_text()),
        prepared=False,
    )
    signature, tree = read(raw)
    fields = tree[1]
    fields["EndConversation"] = fields["EndConverAbort"] = (11, b"")
    fields["StartingList"][1].insert(
        0, (0, {"Active": (11, b"td_deny"), "Index": (4, 1)})
    )
    link = fields["StartingList"][1][1][1]
    link["Active"] = (11, b"td_gate")
    link["ConditionParams"] = (
        15,
        [(0, {"Key": (10, b"permission"), "Value": (10, b"allowed")})],
    )
    fields["EntryList"][1][0][1]["Script"] = (11, b"td_act")
    fields["EntryList"][1][0][1]["ActionParams"] = (
        15,
        [(0, {"Key": (10, b"action"), "Value": (10, b"unchanged")})],
    )
    raw = write(signature, tree)
    (output / "td_original.dlg").write_bytes(raw)
    converted, scripts, _ = prepare_dialogue("td_prepared", raw, 4000000)
    (output / "td_prepared.dlg").write_bytes(converted)
    for name, script in scripts.items():
        # Test-only observation: only wrappers that pass their original condition
        # can reach this point. Do not add instrumentation to production scripts.
        script = script.replace(
            " RWTrNodeVisible(",
            ' SetLocalInt(GetModule(), "td_visible", GetLocalInt(GetModule(), "td_visible")+1);\n RWTrNodeVisible(',
        )
        (output / (name + ".nss")).write_text(script)
    (output / "td_deny.nss").write_text(
        'int StartingConditional(){SetLocalInt(GetModule(),"td_denied",GetLocalInt(GetModule(),"td_denied")+1);return FALSE;}'
    )
    (output / "td_gate.nss").write_text("""#include "rw_tr_nodes"
int StartingConditional(){
 object m=GetModule();SetLocalInt(m,"td_gate_calls",GetLocalInt(m,"td_gate_calls")+1);
 // Headless BeginConversation uses the target NPC as the dialogue owner;
 // GetPCSpeaker is invalid because neither participant is a player.
 int ok=GetScriptParam("permission")=="allowed" && OBJECT_SELF==GetLocalObject(m,"td_partner")
  && !GetIsObjectValid(GetPCSpeaker()) && NWNX_Dialog_GetCurrentNodeID()==0;
 string source=NWNX_Dialog_GetCurrentNodeText(0,0);
 SetLocalInt(OBJECT_SELF,"rw_td_4000000_o0_0",TRUE);SetLocalString(OBJECT_SELF,"rw_td_4000000_o0_0",source);
 NWNX_Dialog_SetCurrentNodeText("<CUSTOM4000000>",0,0);RWTrNodeRestore(4000000);
 WriteTimestampedLogEntry("RW_INV_TEST restore_authored_source "+(NWNX_Dialog_GetCurrentNodeText(0,0)==source && source!=""?"PASS":"FAIL"));
 NWNX_Dialog_SetCurrentNodeText("Changed authored text",0,0);RWTrNodeRestore(4000000);
 WriteTimestampedLogEntry("RW_INV_TEST preserve_runtime_text_change "+(NWNX_Dialog_GetCurrentNodeText(0,0)=="Changed authored text"?"PASS":"FAIL"));
 NWNX_Dialog_SetCurrentNodeText(source,0,0);
 SetLocalInt(m,"td_gate_ok",ok);return ok;
}""")
    (output / "td_act.nss").write_text("""void main(){
 object m=GetModule();SetLocalInt(m,"td_action_calls",GetLocalInt(m,"td_action_calls")+1);
 SetLocalInt(m,"td_action_ok",GetScriptParam("action")=="unchanged" && OBJECT_SELF==GetLocalObject(m,"td_partner")
  && !GetIsObjectValid(GetPCSpeaker()));
}""")


if __name__ == "__main__":
    import sys

    build_fixture(sys.argv[1])
