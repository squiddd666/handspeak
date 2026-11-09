import json, sys, unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from select_handshape_repair import fit_budget,metrics


class HandshapeSelectionTests(unittest.TestCase):
    def test_no_extra_wrong_or_unsupported_accepts(self):
        p=np.asarray([[.85,.1,.05]]*4+[[.1,.85,.05]]*4+[[.45,.4,.15],[.1,.1,.8]],np.float32)
        expected=np.asarray(["A"]*4+["B"]*4+["B","__UNKNOWN__"])
        names=["A","B"];labels=names+["__UNKNOWN__"]
        policy=fit_budget(p,expected,labels,names,{"wrong":0,"negativeFalse":0})
        result=metrics(p,expected,labels,names,policy)
        self.assertEqual(result["correct"],8)
        self.assertEqual(result["wrong"],0);self.assertEqual(result["negativeFalse"],0)
        self.assertEqual(result["attempts"],9);self.assertEqual(result["noMatch"],1)
    def test_tracking_failure_remains_in_denominator(self):
        p=np.asarray([[.9,.05,.05]]*3+[[float("nan")]*3],np.float32)
        expected=np.asarray(["A"]*4)
        policy=fit_budget(p,expected,["A","B","__UNKNOWN__"],["A","B"],{"wrong":0,"negativeFalse":0})
        self.assertEqual(policy["validation"]["attempts"],4)
        self.assertEqual(policy["validation"]["noMatch"],1)
    def test_frozen_actual_weights_and_selection_are_bound(self):
        from asl_model_tools import digest
        report=ROOT/"reports/motion-repair-v3-20261107"
        if not (report/"frozen-selection.json").exists():self.skipTest("Release has not been selected")
        frozen=json.loads((report/"frozen-selection.json").read_text(encoding="utf-8"))
        self.assertFalse(frozen["testUsedForSelection"]);self.assertFalse(frozen["watchClipsUsedForSelection"])
        self.assertEqual(digest(report/"release-draft.json"),frozen["releaseDraftSha256"])
        for family in ("beginner","capstone"):
            selection=json.loads((report/f"selection-{family}.json").read_text(encoding="utf-8"))
            self.assertEqual(digest(report/f"selection-{family}.json"),frozen["selections"][family])
            self.assertEqual(digest(selection["auxiliaryCheckpoint"]),selection["auxiliarySha256"])
            for outcome in selection["selected"].values():
                self.assertLessEqual(outcome["after"]["wrong"],outcome["before"]["wrong"])
                self.assertLessEqual(outcome["after"]["negativeFalse"],outcome["before"]["negativeFalse"])


if __name__=="__main__":unittest.main()
