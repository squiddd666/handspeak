import json,unittest
from scripts.fetch_missing_sign_metadata import parse_source_map


class PublisherMetadataTests(unittest.TestCase):
    def test_exact_gloss_and_original_linkage_are_required_without_execution(self):
        data={s:{'orig_name':{'0':'gtsignstudy4a.1-baby-001.mp4'}} for s in ('train','val','test')}
        html='const sign="baby",ds="popsign_v2_1",dsCategory="game",sourceMap=JSON.parse(\''+json.dumps(data)+'\');malicious();'
        self.assertEqual(parse_source_map(html,'baby'),data)
        self.assertEqual(parse_source_map(html.replace("');malicious();","'),other=1;"),'baby'),data)
        with self.assertRaises(ValueError):parse_source_map(html,'love')
        with self.assertRaises(ValueError):parse_source_map(html.replace('popsign_v2_1','popsign_v1_0'),'baby')
    def test_missing_original_identity_cannot_be_called_new_data(self):
        data={s:{'prev_name':{'0':'0-baby.mp4'}} for s in ('train','val','test')}
        html='const sign="baby",ds="popsign_v2_1",dsCategory="game",sourceMap=JSON.parse(\''+json.dumps(data)+'\');'
        with self.assertRaises(ValueError):parse_source_map(html,'baby')


if __name__=='__main__':unittest.main()
