import json,tempfile,unittest
from pathlib import Path
from scripts.prepare_manual_recovery_audit import verified_candidate
from scripts.run_online_native_audit import sha


class RecoveryAuditFreezeTests(unittest.TestCase):
    def test_changed_or_unverified_candidates_cannot_be_acquired_for_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'candidate.json').write_text('{}')
            digest=sha(root/'candidate.json')
            report=dict(modelSha256=digest,testUsedForSelection=False,auditOutcomesRead=False,deployed=False)
            parity=dict(modelSha256=digest,baselineIdentical=True,guardIdentical=True,recoveryIdentical=True)
            (root/'validation.json').write_text(json.dumps(report));(root/'runtime-parity.json').write_text(json.dumps(parity))
            self.assertEqual(verified_candidate(root),digest)
            (root/'candidate.json').write_text('{"changed":true}')
            with self.assertRaises(ValueError):verified_candidate(root)
    def test_reading_audit_outcomes_for_selection_disqualifies_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'candidate.json').write_text('{}');digest=sha(root/'candidate.json')
            (root/'validation.json').write_text(json.dumps(dict(modelSha256=digest,testUsedForSelection=False,auditOutcomesRead=True,deployed=False)))
            (root/'runtime-parity.json').write_text(json.dumps(dict(modelSha256=digest,baselineIdentical=True,guardIdentical=True,recoveryIdentical=True)))
            with self.assertRaises(ValueError):verified_candidate(root)


if __name__=='__main__':unittest.main()
