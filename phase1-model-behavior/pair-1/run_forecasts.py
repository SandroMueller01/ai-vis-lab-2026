"""
TiRex-2 forecasts of the 2 m temperature for the Phase I evaluation (temperature history of one point only).

For every start time and every point of the Austria 15 km dataset, TiRex-2 gets the last 672 h (28 days) of
temperature as context and forecasts the next 24 h as 9 quantiles (0.1 ... 0.9). No other variable and no
neighbouring point is given to the model. Gaps in the temperature are filled linearly inside the series and
at its ends with the nearest value.

Start times:
  grid     every 10 days, starting 29 days after the first hour, at 00, 03, 06, 09, 12, 15, 18, 19 and 21 UTC
           (306 start times at most, to answer how often and when the model is wrong)
  front-12 12 h before the peak of each cold front in data/austria_15km/fronts.csv
  front-6  6 h before the peak of each cold front
           (a front needs 672 h of history before it, so the first front of the year has no front run)

Output: one .npz file with
  preds       (start times, points, 9 quantiles, 24 h) float16
  origin_idx  index of the first forecast hour in the hourly time axis
  tags        "grid", "front-12" or "front-6" per start time
  pids        point ids, times  hourly time axis (ns since epoch, UTC)

Run time: about 14 s per start time on a normal CPU (about 75 minutes for the defaults).

Usage:
  python phase1-model-behavior/pair-1/run_forecasts.py
  python phase1-model-behavior/pair-1/run_forecasts.py --step-days 30      # fewer start times, for a quick test
Data: GeoSphere Austria, https://data.hub.geosphere.at (CC BY 4.0). Model: TiRex-2 (Apache 2.0).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DATA = Path(__file__).resolve().parents[2] / "data"
START_HOURS = [0, 3, 6, 9, 12, 15, 18, 19, 21]
FRONT_LEADS = (12, 6)


def temperature(path: Path) -> pd.DataFrame:
    """grid_long.parquet -> hourly (time x point) temperature without gaps."""
    g = pd.read_parquet(path, columns=["point_id", "time", "T2M"])
    t = g.pivot(index="time", columns="point_id", values="T2M")
    return t.interpolate(limit_area="inside").ffill().bfill()


def start_times(times: pd.DatetimeIndex, fronts: pd.DataFrame, context: int, horizon: int, step_days: int):
    """(index of the first forecast hour, tag) for the spread-out and the front start times."""
    out = []
    days = pd.date_range(times[0] + pd.Timedelta(days=29), times[-1] - pd.Timedelta(days=2), freq=f"{step_days}D").normalize()
    for d in days:
        for h in START_HOURS:
            out.append((times.get_loc(d + pd.Timedelta(hours=h)), "grid"))
    for peak in fronts[fronts.cold_front].peak_time:
        for lead in FRONT_LEADS:
            i = times.get_loc(peak) - lead
            if i >= context and i + horizon <= len(times):
                out.append((i, f"front-{lead}"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(REPO_DATA / "austria_15km"), help="dataset folder with grid_long.parquet and fronts.csv")
    ap.add_argument("--out", default=None, help="output file (default: <data>/tirex2_forecasts.npz)")
    ap.add_argument("--context", type=int, default=672, help="hours of history given to the model")
    ap.add_argument("--horizon", type=int, default=24, help="hours to forecast")
    ap.add_argument("--step-days", type=int, default=10, help="days between the spread-out start days")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    import torch
    from tirex2 import TimeseriesType, load_model

    data = Path(args.data)
    out = Path(args.out) if args.out else data / "tirex2_forecasts.npz"
    t = temperature(data / "grid_long.parquet")
    times, pids = t.index, t.columns.to_numpy()
    series = t.to_numpy(np.float32)
    fronts = pd.read_csv(data / "fronts.csv", parse_dates=["peak_time"])
    origins = start_times(times, fronts, args.context, args.horizon, args.step_days)
    print(f"{len(origins)} start times x {len(pids)} points", flush=True)

    model = load_model("NX-AI/TiRex-2", device=args.device)
    preds = np.zeros((len(origins), len(pids), 9, args.horizon), np.float16)
    t0 = time.time()
    for k, (i, _) in enumerate(origins):
        context = torch.from_numpy(series[i - args.context : i].T.copy())
        batch = [TimeseriesType(target=context[j][None], past_covariates=None, future_covariates=None) for j in range(len(pids))]
        forecast = model.forecast(batch, prediction_length=args.horizon, output_type="numpy", batch_size=128)
        preds[k] = np.stack([f[0] for f in forecast])
        if k % 20 == 0:
            print(f"{k}/{len(origins)} {time.time() - t0:.0f}s", flush=True)
    np.savez_compressed(
        out, preds=preds, origin_idx=np.array([o[0] for o in origins]), tags=np.array([o[1] for o in origins]),
        pids=pids, times=times.astype("int64").to_numpy(),
    )
    print(f"done in {time.time() - t0:.0f}s: {out}")


if __name__ == "__main__":
    main()
