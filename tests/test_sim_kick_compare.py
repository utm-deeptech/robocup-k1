"""A gate decision must not accept duplicated or truncated trial evidence."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sim_kick_compare import validate_completed_windows


class ComparisonIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.protocol = {'positions': [[0, 0], [1, -1], [1, 1], [2, -2], [2, 2]],
                         'observation_window_sim_s': 120}
        self.results = [{'trial': trial, 'requested_ball_x': self.protocol['positions'][(trial-1)%5][0],
                         'requested_ball_y': self.protocol['positions'][(trial-1)%5][1],
                         'start_sim_time': trial*200, 'observation_end_sim_time': trial*200+120,
                         'reason': 'fixed_sim_window_complete'} for trial in range(1, 21)]
        self.classifications = [{'trial': trial, 'observed_play_duration_s': 119.98}
                                for trial in range(1, 21)]

    def test_complete_recording_passes(self):
        validate_completed_windows(self.results, self.classifications, self.protocol)

    def test_duplicate_trial_fails_even_with_twenty_rows(self):
        self.results[-1] = copy.deepcopy(self.results[0])
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            validate_completed_windows(self.results, self.classifications, self.protocol)

    def test_declared_window_cannot_hide_truncated_raw_data(self):
        self.classifications[4]['observed_play_duration_s'] = 20
        with self.assertRaisesRegex(ValueError, 'Raw recording'):
            validate_completed_windows(self.results, self.classifications, self.protocol)

    def test_wrong_position_fails(self):
        self.results[4]['requested_ball_y'] = 0
        with self.assertRaisesRegex(ValueError, 'starting position'):
            validate_completed_windows(self.results, self.classifications, self.protocol)

    def test_incomplete_window_fails(self):
        self.results[4]['observation_end_sim_time'] -= 5
        with self.assertRaisesRegex(ValueError, 'Incomplete observation'):
            validate_completed_windows(self.results, self.classifications, self.protocol)


if __name__ == '__main__':
    unittest.main()
