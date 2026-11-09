import unittest
from scripts.freeze_browser_domain_guard_audit import render

class BodyContextGuardAuditTests(unittest.TestCase):
    def test_fixture_allowlist_survives_html_render(self):
        cfg=dict(items=[],allowedFiles={'/training/experimental/browser_domain_guard_audit_page.mjs':'exact/path'},token='token')
        html=render(cfg);value=html.split('window.DUAL_CAPTURE_FIXTURE = ',1)[1].split(';</script>',1)[0]
        import json
        self.assertEqual(json.loads(value),cfg)
        self.assertIn('No fitting',html)

if __name__=='__main__':unittest.main()
