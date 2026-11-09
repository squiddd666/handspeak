import unittest
from scripts.resolve_popsign_v2_provenance import identity,screen

class PopSignIdentityTests(unittest.TestCase):
    def test_renamed_ids_have_same_conservative_recording_key(self):
        a=identity('4a.8032-baby-2023_09_28_19_00_54.286-1.mp4')
        b=identity('16f0-baby-2023_09_28_19_00_54.286-1.mp4')
        self.assertEqual(a['recordingKey'],b['recordingKey']);self.assertNotEqual(a['participant'],b['participant'])
    def test_screen_excludes_renamed_recordings_and_fitting_links(self):
        names={'0':'16f0-baby-2023_09_28_19_00_54.286-1.mp4','1':'66d7-baby-2023_09_29_19_00_54.286-1.mp4','2':'3d3f-baby-2023_09_30_19_00_54.286-1.mp4'}
        source=dict(test=dict(orig_name=names,prev_name=dict(names),size={'orig_name':3,'prev_name':3}))
        known={identity(names['0'])['recordingKey']};result=screen(source,'baby',known,{'7043'},{'66d7':['7043']})
        self.assertEqual([r['anonymousParticipant'] for r in result['selected']],['3d3f'])
        self.assertFalse(result['newSignerVerified']);self.assertTrue(result['originalContentHashesPending'])
    def test_related_glosses_and_changed_previous_identities_are_not_substituted(self):
        names={'0':'16f0-wantto-2023_09_28_19_00_54.286-1.mp4'}
        source=dict(test=dict(orig_name=names,prev_name=dict(names),size={'orig_name':1,'prev_name':1}))
        with self.assertRaises(ValueError):screen(source,'want',set(),set(),{})
        source['test']['orig_name']['0']=names['0'].replace('wantto','baby')
        result=screen(source,'baby',set(),set(),{});self.assertEqual(result['metadataEligible'],0)
    def test_unsafe_or_unknown_name_is_not_an_identity(self):
        self.assertIsNone(identity('preview-baby.mp4'))

if __name__=='__main__':unittest.main()
