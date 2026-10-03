import json
from pathlib import Path
import tempfile
import unittest

from lexical_source_leads import translation_matches
from prepare_joint_experiment import assemble
import train_expansion_batch as batch


class JointSourcesTests(unittest.TestCase):
    def test_translation_candidates_exclude_guesses_and_substrings(self):
        self.assertFalse(translation_matches('AMBULANCE', {
            'NondominantTranslations': 'ambulance, smoke',
            'SignBankEnglishTranslations': 'boil, simmer'}))
        self.assertFalse(translation_matches('RICE', {'SignBankEnglishTranslations': 'price'}))
        self.assertFalse(translation_matches("DON'T TOUCH", {'SignBankEnglishTranslations': 'touch'}))
        self.assertTrue(translation_matches("YOU'RE WELCOME", {
            'SignBankEnglishTranslations': "greeting, welcome, you're welcome"}))

    def test_merge_deduplicates_but_rejects_conflicting_identity_and_test_data(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.json'
            row = dict(label='BOOK', split='train', participant='a', sha256='one', sequence=[[1]])
            catalog = dict(items=[dict(label='BOOK')])
            source.write_text(json.dumps([row, row]))
            rows, labels, _ = assemble([source], catalog)
            self.assertEqual(len(rows), 1)
            self.assertEqual(labels, ['BOOK'])
            for other in [dict(row, label='RICE'), dict(row, split='val'),
                          dict(row, participant='b'), dict(row, split='test', sha256='two'),
                          dict(row, split='val', sha256='two')]:
                source.write_text(json.dumps([row, other]))
                with self.assertRaises(ValueError):
                    assemble([source], catalog)

    def test_custom_labels_require_coverage_and_negative_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'input.json'
            rows = [dict(label=label, split=split, participant=split,
                         sha256=f'{split}-{label}', sequence=[[1]], rawFrames=[])
                    for split in ('train', 'val') for label in ('BOOK', 'OTHER')]
            source.write_text(json.dumps(rows))
            for labels in ([], ['BOOK', 'BOOK'], ['ABSENT'], ['BOOK', 'OTHER'], [' BOOK']):
                with self.assertRaises(ValueError):
                    batch.prepare(source, root / 'out', labels=labels)
            train, val = batch.prepare(source, root / 'out', labels=['BOOK'])
            self.assertEqual(len(train), 2)
            self.assertEqual(len(val), 2)
            self.assertEqual(json.loads((root / 'out/protocol.json').read_text())['labels'], ['BOOK'])


if __name__ == '__main__':
    unittest.main()
