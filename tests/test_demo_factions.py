import unittest
try:
    from demo.investigation.factions import build
except ModuleNotFoundError:
    build = None
from tools.gff import read
@unittest.skipIf(build is None, "Demo sources are not included in the server-only archive")
class DemoFactionTests(unittest.TestCase):
    def test_encounter_factions_are_separate_and_neutral(self):
        signature, root = read(build())
        self.assertEqual(signature,b"FAC V3.2")
        rows=root[1]["FactionList"][1]
        self.assertEqual(len(rows),8)
        for i in (5,6,7): self.assertEqual(rows[i][1]["FactionGlobal"][1],0)
        reps={(r[1]["FactionID1"][1],r[1]["FactionID2"][1]):r[1]["FactionRep"][1] for r in root[1]["RepList"][1]}
        for i in (5,6,7):
            for j in range(8): self.assertEqual(reps[i,j],100 if i==j else 50)
