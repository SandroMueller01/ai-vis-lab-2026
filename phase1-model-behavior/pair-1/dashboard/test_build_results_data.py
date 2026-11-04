"""Offline checks for the helper functions of the results data on small synthetic inputs."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

# Support discovery and direct execution from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_results_data import arrival, neighbour_counts, pack_runs, time_longitude, unpack_runs, why_not


class ResultsDataTests(unittest.TestCase):
    def test_neighbour_counts_on_a_lattice(self):
        x, y = np.meshgrid(np.arange(3) * 15000, np.arange(3) * 15000)
        x, y = np.append(x.ravel(), 90000), np.append(y.ravel(), 90000)  # one isolated point
        counts = neighbour_counts(x, y, 15000).reshape(-1)
        self.assertEqual(counts[4], 4)  # centre
        self.assertEqual(sorted(counts[[0, 2, 6, 8]]), [2, 2, 2, 2])  # corners
        self.assertEqual(sorted(counts[[1, 3, 5, 7]]), [3, 3, 3, 3])  # edges
        self.assertEqual(counts[9], 0)

    def test_pack_and_unpack_keep_a_twentieth_of_a_degree(self):
        rng = np.random.default_rng(0)
        parts = [rng.uniform(-20, 35, (2, 3, n)) for n in (36, 24, 24, 24, 24)]
        packed = pack_runs(*parts)
        self.assertEqual(packed.shape, (2, 3, 36 + 4 * 24))
        for before, after in zip(parts, unpack_runs(packed)):
            self.assertLessEqual(np.abs(before - after).max(), 0.05 + 1e-6)

    def test_arrival_is_the_first_passage_hour_within_12_h_of_the_peak(self):
        onset = np.zeros((80, 3), bool)
        onset[[25, 40], 0] = True  # first one counts
        onset[60, 2] = True  # 30 h after the peak: outside the window
        self.assertEqual(arrival(onset, 30).tolist(), [25, -1, -1])

    def test_why_not_names_every_failed_rule(self):
        ok = SimpleNamespace(r2=0.6, speed_ms=5.0, moves_to_deg=150.0)
        self.assertEqual(why_not(ok), "a moving line from the west or north")
        bad = SimpleNamespace(r2=0.05, speed_ms=35.0, moves_to_deg=5.0)
        text = why_not(bad)
        self.assertIn("moving line", text)
        self.assertIn("km/h", text)
        self.assertIn("west or north", text)

    def test_time_longitude_averages_the_points_of_each_strip(self):
        anom = np.zeros((100, 4))
        anom[:, 0], anom[:, 1], anom[:, 2], anom[:, 3] = 1.0, 3.0, 5.0, 7.0
        lon = np.array([9.5, 9.6, 10.6, 10.7])
        z = time_longitude(anom, lon, 50, np.array([9.4, 9.9, 10.4, 10.9]))
        self.assertEqual(z.shape, (36, 3))
        self.assertTrue(np.allclose(z[:, 0], 2.0))  # points 0 and 1
        self.assertTrue(np.isnan(z[:, 1]).all())  # no point in this strip
        self.assertTrue(np.allclose(z[:, 2], 6.0))  # points 2 and 3


if __name__ == "__main__":
    unittest.main()
