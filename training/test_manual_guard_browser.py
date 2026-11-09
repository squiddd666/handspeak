import copy,tempfile,unittest
from pathlib import Path
from training.test_online_worker_audit import WorkerAuditTests
from scripts.serve_manual_guard_browser import GuardStore
from scripts.freeze_manual_guard_browser import render_fixture


class FixtureRenderingTests(unittest.TestCase):
    def test_embedded_allowlist_is_not_rewritten(self):
        import json
        cfg={'allowedFiles':{'/training/experimental/online_worker_audit_page.mjs':'original',
            '/training/experimental/manual_guard_browser_page.mjs':'guard'},'items':[]}
        html=render_fixture(cfg)
        start=html.index('window.DUAL_CAPTURE_FIXTURE = ')+len('window.DUAL_CAPTURE_FIXTURE = ')
        self.assertEqual(json.loads(html[start:html.index(';</script>',start)]),cfg)
        self.assertEqual(html.count('src="/training/experimental/manual_guard_browser_page.mjs"'),1)


class GuardBrowserStoreTests(WorkerAuditTests):
    def setUp(self):
        super().setUp();self.store=GuardStore(Path(self.temp.name)/'guard-ledger',self.cfg,self.receipts)
        self.report['schema']=5
        a=self.report['attempts'][0];a['manualPredictions']['default']='HELLO'
        a['manualGuardPredictions']=dict(default=None,expanded=None,daily=None,pack=None)
        a['manualGuardReasons']=dict(default='open-set-veto',expanded='baseline-rejected',daily='baseline-rejected',pack='baseline-rejected')
    def test_guard_cannot_add_or_change_a_baseline_prediction(self):
        r=copy.deepcopy(self.report);r['attempts'][0]['manualGuardPredictions']['default']='NO'
        with self.assertRaises(ValueError):self.store.save(r)
    def test_guard_checkpoint_preserves_rejection_separately(self):
        self.assertEqual(self.store.save(self.report),1)
        self.assertTrue((self.store.guard_folder/'attempt-001.json').exists())
        self.assertEqual(self.store.save(self.report),1)
        r=copy.deepcopy(self.report);r['attempts'][0]['manualGuardPredictions']['default']='HELLO'
        with self.assertRaises(ValueError):self.store.save(r)


if __name__=='__main__':unittest.main()
