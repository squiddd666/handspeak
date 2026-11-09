"""Reference diagnosis never upgrades a suggestion into an accepted word."""
import copy
import unittest

from scripts.report_motion_repair_v4 import diagnose, transitions


def take(**changes):
    row = dict(label="HELLO", clip="hello.mp4", clipSha256="digest", family="beginner", vocabulary=None,
               correct=False, predicted=None, status="No reliable match", response={"suggestions": [{"label": "HELLO"}]})
    row.update(changes)
    return row


class RepairV4ReportTests(unittest.TestCase):
    def test_correct_suggestion_is_still_a_rejection(self):
        self.assertEqual(diagnose(take()), "correct top suggestion rejected")

    def test_competitor_and_accepted_error_are_distinct(self):
        self.assertEqual(diagnose(take(response={"suggestions": [{"label": "DRINK"}]})), "competing top suggestion rejected")
        self.assertEqual(diagnose(take(predicted="DRINK")), "accepted wrong label")

    def test_tracking_gate_overrules_unaccepted_suggestions(self):
        self.assertEqual(diagnose(take(status="Not enough tracked frames")), "insufficient tracking")

    def test_manual_no_match_is_not_server_error(self):
        self.assertEqual(diagnose(take(family="motion-manual", response={})), "no accepted manual match")

    def test_changed_reference_or_route_is_rejected(self):
        for changes in ({"clipSha256": "changed"}, {"family": "capstone"}, {"vocabulary": "full"}):
            with self.assertRaises(ValueError):
                transitions({"hello": take()}, {"hello": take(**changes)})

    def test_missing_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            transitions({"hello": take()}, {})

    def test_regression_is_retained_without_modifying_input(self):
        old, new = {"hello": take(correct=True, predicted="HELLO")}, {"hello": take(predicted="DRINK")}
        original = copy.deepcopy(new)
        result = transitions(old, new)
        self.assertEqual((result[0]["before"], result[0]["after"]), ("matched", "wrong"))
        self.assertEqual(new, original)


if __name__ == "__main__":
    unittest.main()
