"""Offline checks for the dashboard data encoding on small synthetic series."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Support discovery and direct execution from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dashboard_data import decode, encode, quantise, spacing_km


class EncodingTests(unittest.TestCase):
    def test_round_trip_is_exact_for_smooth_series(self):
        t = np.arange(200)
        q = np.column_stack([100 + 30 * np.sin(t / 20), 50 + t * 0.5]).round().astype(np.int16)
        np.testing.assert_array_equal(decode(*encode(q)), q)

    def test_large_jump_is_caught_up_and_never_adds_up(self):
        q = np.full((6, 1), 10, dtype=np.int16)
        q[2:, 0] = 250  # +240 in one hour, more than an int8 difference can hold
        self.assertEqual(decode(*encode(q))[:, 0].tolist(), [10, 10, 137, 250, 250, 250])

    def test_quantisation_error_stays_below_half_a_step(self):
        x = np.array([-22.5, -5.54, 0.0, 17.3, 39.9])
        q = quantise(x, lo=-25.0, step=0.27)
        self.assertLessEqual(np.abs(-25.0 + q * 0.27 - x).max(), 0.135 + 1e-9)

    def test_rain_uses_a_square_root_scale_and_clips(self):
        mm = np.array([0.0, 0.1, 1.0, 5.0, 30.0, 96.0])
        q = quantise(mm, lo=0.0, step=0.0215, sqrt=True)
        back = (q * 0.0215) ** 2
        self.assertTrue((np.abs(back[:5] - mm[:5]) <= 0.05 * np.maximum(mm[:5], 1)).all())  # fine steps for light rain
        self.assertEqual(q[-1], 255)  # far above the range: clipped, not wrapped

    def test_spacing_is_the_nearest_neighbour_distance_rounded_to_5_km(self):
        step_lat = 15 / 111.2
        step_lon = 15 / (111.2 * np.cos(np.radians(47)))
        points = pd.DataFrame(
            [(47 + i * step_lat, 13 + j * step_lon) for i in range(5) for j in range(5)], columns=["lat", "lon"]
        )
        self.assertEqual(spacing_km(points), 15)


if __name__ == "__main__":
    unittest.main()
