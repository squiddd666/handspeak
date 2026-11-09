import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import handshape_inference as inference


class HandshapeInferenceTests(unittest.TestCase):
    def test_probability_mass_retains_unknown(self):
        p=inference.combine(np.asarray([.8,.2]),np.asarray([.1,.2,.7]),["A","B"],["A","B","__UNKNOWN__"],.5)
        np.testing.assert_allclose(p,[.45,.2,.35]);self.assertAlmostEqual(float(p.sum()),1)
    def test_reorders_vocabulary(self):
        p=inference.combine(np.asarray([.8,.2]),np.asarray([.2,.1,.7]),["A","B"],["B","A","__UNKNOWN__"],1)
        np.testing.assert_allclose(p,[.1,.2,.7])
    def test_absent_configuration_preserves_base_exactly(self):
        with patch.object(inference,"configuration",return_value=None):
            p=np.asarray([.3,.7]);labels=["A","B"]
            result,names,metadata=inference.fuse("beginner","digest",p,labels,[])
            self.assertIs(result,p);self.assertIs(names,labels);self.assertEqual(metadata,{})
    def test_configuration_fails_closed_on_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/"models").mkdir();config=root/"config.json"
            config.write_text(json.dumps({"models":{"beginner":{"checkpointSha256":"base","auxiliary":{
                "checkpoint":"models/aux.pt","checkpointSha256":"expected","featureVersion":"body-handshape-v1","weights":{"full":.5}}}}}))
            with patch.object(inference,"CONFIG",config),patch.object(inference,"REPO",root),patch.object(inference,"checkpoint_digest",return_value="different"):
                with self.assertRaises(ValueError):inference.configuration("beginner","base")
                self.assertIsNone(inference.configuration("beginner","stale"))
    def test_unknown_never_becomes_word(self):
        from motion_calibration import decide
        d=decide([.1,.1,.8],["A","B","__UNKNOWN__"],allowed=[0,1],policy={"minVocabularyMass":.6})
        self.assertFalse(d["predictions"]);self.assertEqual(d["rejectionReason"],"outside-vocabulary")
        self.assertNotIn("__UNKNOWN__",[r["label"] for r in d["suggestions"]])
    def test_selected_practice_label_is_not_an_input(self):
        import inspect
        parameters=inspect.signature(inference.fuse).parameters
        self.assertNotIn("expected",parameters);self.assertNotIn("practiceLabel",parameters)


if __name__=="__main__":unittest.main()
