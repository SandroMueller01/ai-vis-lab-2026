"""Offline checks for the shared event definitions on small synthetic series."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Support discovery and direct execution from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "events"))
from build_events import cold_wave_days, deltas, episodes, flags


def frame(values):
    """Hourly (time x location) frame starting 2026-03-01 00:00 UTC."""
    index = pd.date_range("2026-03-01", periods=len(values), freq="1h", tz="UTC")
    return pd.DataFrame(values, index=index, columns=range(np.shape(values)[1]))


class EventTests(unittest.TestCase):
    def setUp(self):
        hours = 96
        daily = 5 * np.sin(np.arange(hours) / 24 * 2 * np.pi)  # same every day -> dT24 == 0
        t2m = np.column_stack([daily, daily, daily])
        t2m[60:70, 0] -= 10  # location 0: 10 K colder than the day before for 10 h
        t2m[40:, 1] -= 4  # location 1: 4 K drop within one hour ...
        rr = np.zeros_like(t2m)
        rr[40, 1] = 3  # ... with 3 mm rain -> thunderstorm
        t2m[20:22, 2] = np.nan  # location 2: 2 h gap, gets filled
        self.t2m, self.rr = frame(t2m), frame(rr)

    def test_deltas_remove_daily_cycle_and_fill_short_gaps(self):
        dt24, dt1 = deltas(self.t2m, max_gap=3)
        self.assertTrue(dt24.iloc[:24].isna().all().all())  # no day before
        self.assertAlmostEqual(dt24.iloc[30:60, 0].abs().max(), 0, places=6)
        self.assertFalse(dt1.iloc[1:, 2].isna().any())

    def test_long_gaps_stay_empty_and_never_produce_events(self):
        t2m = self.t2m.copy()
        t2m.iloc[50:60, 2] = np.nan
        dt24, dt1 = deltas(t2m, max_gap=3)
        self.assertTrue(dt24.iloc[50:60, 2].isna().all())  # not even the first 3 hours get filled
        self.assertTrue(dt24.iloc[60:70, 2].notna().all())
        self.assertFalse(flags(dt24, dt1, self.rr)["cold_drop"].iloc[:, 2].any())

    def test_flags(self):
        dt24, dt1 = deltas(self.t2m)
        f = flags(dt24, dt1, self.rr)
        cold, storm = f["cold_drop"], f["thunderstorm"]
        self.assertEqual(cold[0].sum(), 10)
        self.assertEqual(cold.iloc[:, 1:].to_numpy().sum(), 0)  # -4 K is not a cold drop
        self.assertEqual(list(storm.index[storm[1]]), [self.t2m.index[40]])
        self.assertEqual(storm.to_numpy().sum(), 1)

    def test_rain_without_drop_is_no_thunderstorm(self):
        rr = self.rr.copy()
        rr.iloc[10, 0] = 20
        dt24, dt1 = deltas(self.t2m)
        self.assertEqual(flags(dt24, dt1, rr)["thunderstorm"].to_numpy().sum(), 1)

    def test_episodes_merge_close_hours_per_location(self):
        mask = frame(np.zeros((30, 2), dtype=bool))
        mask.iloc[[2, 4, 20], 0] = True  # 2 h apart -> one episode; 16 h later -> new one
        mask.iloc[3, 1] = True  # other location -> own episode
        ti, loc, ep = episodes(mask, gap=6)
        self.assertEqual(list(zip(ti, loc, ep)), [(2, 0, 0), (4, 0, 0), (20, 0, 1), (3, 1, 2)])

    def test_cold_wave_days(self):
        dt24, dt1 = deltas(self.t2m)
        cold = flags(dt24, dt1, self.rr)["cold_drop"]
        days = cold_wave_days(cold, dt24.notna(), share=0.25)
        day = days.loc[pd.Timestamp("2026-03-03").date()]
        self.assertEqual(days.cold_wave.sum(), 1)  # 1 of 3 locations on 2026-03-03
        self.assertAlmostEqual(day.share, 1 / 3)
        self.assertEqual(day.peak_time, self.t2m.index[60])  # first hour of the drop
        self.assertEqual(cold_wave_days(cold, dt24.notna(), share=0.5).cold_wave.sum(), 0)

    def test_scattered_drops_are_no_cold_wave(self):
        cold = frame(np.zeros((48, 4), dtype=bool))
        for loc in range(4):
            cold.iloc[24 + 5 * loc, loc] = True  # every location, but never at the same hour
        days = cold_wave_days(cold, frame(np.ones((48, 4), dtype=bool)), share=0.5)
        self.assertEqual(days.cold_wave.sum(), 0)
        self.assertAlmostEqual(days.share.max(), 0.25)


if __name__ == "__main__":
    unittest.main()
