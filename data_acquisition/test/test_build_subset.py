"""Offline checks for the coarse-lattice point selection."""

import sys
import unittest
from pathlib import Path

import pandas as pd

# Support discovery and direct execution from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "austria_15km"))
from build_subset import select

POINTS_5KM = Path(__file__).resolve().parents[1] / "austria_5km" / "austria_points_5km.csv"


class SubsetTests(unittest.TestCase):
    def test_keeps_only_multiples_of_the_spacing(self):
        points = pd.DataFrame({"point_id": range(4), "x": [0, 5000, 15000, 15000], "y": [0, 15000, 30000, 10000]})
        self.assertEqual(select(points, 15).point_id.tolist(), [0, 2])

    def test_austria_lattice_sizes(self):
        points = pd.read_csv(POINTS_5KM)
        self.assertEqual(len(select(points, 5)), len(points))
        self.assertEqual(len(select(points, 15)), 378)
        self.assertLess(len(select(points, 20)), len(select(points, 10)))


if __name__ == "__main__":
    unittest.main()
