"""Check measurement math against known trajectories and full-ball boundaries."""
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sim_kick_metrics import boundary_result, direction, wrap
from sim_kick_baseline import summary


class KickMetricsTest(unittest.TestCase):
    def test_signed_direction_in_all_quadrants(self):
        for degrees in (-179, -100, -45, 0, 50, 150, 179):
            theta = math.radians(degrees)
            times = (0, 0.02, 0.07, 0.11, 0.25)
            points = [(100 + t, 2 + 3 * t * math.cos(theta), -1 + 3 * t * math.sin(theta)) for t in times]
            self.assertAlmostEqual(wrap(direction(points) - theta), 0, places=10)

    def test_angle_wrap_avoids_358_degree_error(self):
        self.assertAlmostEqual(math.degrees(wrap(math.radians(-179 - 179))), 2)

    def test_stationary_and_insufficient_data_have_no_direction(self):
        self.assertIsNone(direction([(0, 0, 0), (1, 0, 0), (2, 0, 0)]))
        self.assertIsNone(direction([(0, 0, 0), (1, 1, 0)]))

    def test_full_ball_crossing_and_posts(self):
        self.assertIsNone(boundary_result((7.10, 0, 0.11)))
        self.assertEqual(boundary_result((7.14, 0, 0.11)), 'goal')
        self.assertEqual(boundary_result((7.14, 1.25, 0.11)), 'wide')
        self.assertIsNone(boundary_result((0, 4.6, 0.11)))
        self.assertEqual(boundary_result((0, 4.64, 0.11)), 'out')

    def test_summary_keeps_failed_trials_in_goal_denominator(self):
        rows = [{'result': 'goal', 'aim_error_deg': -10},
                {'result': 'out', 'aim_error_deg': 30},
                {'result': 'missed_contact'}, {'result': 'missed_contact'}]
        with tempfile.TemporaryDirectory() as folder:
            result = summary(rows, Path(folder))
        self.assertEqual(result['goal_percent'], 25)
        self.assertEqual(result['trials_with_direction'], 2)
        self.assertEqual(result['mean_absolute_aim_error_deg'], 20)
        self.assertEqual(result['max_absolute_aim_error_deg'], 30)

    def test_no_launch_is_missing_measurement_not_zero_error(self):
        with tempfile.TemporaryDirectory() as folder:
            result = summary([{'result': 'missed_contact'}], Path(folder))
        self.assertIsNone(result['mean_absolute_aim_error_deg'])
        self.assertIsNone(result['max_absolute_aim_error_deg'])


if __name__ == '__main__':
    unittest.main()
