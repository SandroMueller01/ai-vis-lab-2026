"""
Data files for the Phase I dashboard (site/index.html), built from the Austria 15 km dataset
(data/austria_15km, see data_acquisition/austria_15km/README.md and data_acquisition/events/).

Every variable becomes one small binary file, site/data/obs/<VAR>.bin, with time as the slow axis:
  - values are quantised to one byte: round((x - lo) / step), RR on a square-root scale
  - the first row (all points, hour 0) is stored as it is, every later row as the difference to the
    previous hour (int8). The encoder works in a closed loop, so a jump larger than 127 steps is
    caught up in the next hour and the error never adds up
  - short gaps are filled linearly; the browser adds the rows up again
The files are small enough to be committed and served by GitHub Pages.

Also written to site/data/:
  meta.json     points (id, lon, lat), time axis, quantisation of each variable, spacing, jump-to presets
  events.json   cold_front, thunderstorm and cold_drop as (hour index, point index) pairs

Usage:
  python build_dashboard_data.py                          # data/austria_15km -> site/data
  python build_dashboard_data.py --data data/austria_15km --out site/data
Data: GeoSphere Austria, https://data.hub.geosphere.at (CC BY 4.0).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_DATA = HERE.parents[2] / "data"

# stored byte q = round((f(x * factor) - lo) / step), x = lo + q * step (squared back if sqrt)
VARIABLES = {
    "T2M": {"lo": -25.0, "step": 0.27, "unit": "°C"},
    "TD2M": {"lo": -30.0, "step": 0.22, "unit": "°C"},
    "RH2M": {"lo": 0.0, "step": 0.4, "unit": "%"},
    "P0": {"lo": 980.0, "step": 0.24, "unit": "hPa", "factor": 0.01},  # Pa -> hPa
    "UU": {"lo": -25.0, "step": 0.2, "unit": "m/s"},
    "VV": {"lo": -25.0, "step": 0.2, "unit": "m/s"},
    "GL": {"lo": 0.0, "step": 4.8, "unit": "W/m²"},
    "RR": {"lo": 0.0, "step": 0.0215, "unit": "mm", "sqrt": True},  # up to 30 mm per hour
}
KINDS = ["cold_front", "thunderstorm", "cold_drop"]


def quantise(x: np.ndarray, lo: float, step: float, sqrt: bool = False) -> np.ndarray:
    """Float values -> integers 0..255."""
    if sqrt:
        x = np.sqrt(np.clip(x, 0, None))
    return np.clip(np.round((x - lo) / step), 0, 255).astype(np.int16)


def encode(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(time x point) integers -> first row (uint8) and hourly differences (int8), closed loop."""
    recon = q[0].astype(np.int16)
    deltas = np.empty((len(q) - 1, q.shape[1]), dtype=np.int8)
    for t in range(1, len(q)):
        d = np.clip(q[t] - recon, -127, 127)
        deltas[t - 1] = d
        recon = recon + d
    return q[0].astype(np.uint8), deltas


def decode(first: np.ndarray, deltas: np.ndarray) -> np.ndarray:
    """Inverse of encode (what the browser does)."""
    return np.vstack([first, first + np.cumsum(deltas.astype(np.int16), axis=0)]).astype(np.uint8)


def load(path: Path):
    """grid_long.parquet -> points, hourly time axis and one (time x point) frame per variable."""
    cols = ["point_id", "time", "lat", "lon", *VARIABLES]
    df = pd.read_parquet(path, columns=cols)
    points = df.groupby("point_id")[["lat", "lon"]].first().sort_index()
    full = pd.date_range(df.time.min(), df.time.max(), freq="1h")
    wide = {}
    for name in VARIABLES:
        w = df.pivot(index="time", columns="point_id", values=name).reindex(full)[points.index]
        wide[name] = w.interpolate(limit_area="inside").ffill().bfill()
    return points, full, wide


def spacing_km(points: pd.DataFrame) -> int:
    """Typical distance to the nearest other point, rounded to 5 km."""
    lat, lon = np.radians(points.lat.to_numpy()), np.radians(points.lon.to_numpy())
    dx = (lon[:, None] - lon[None, :]) * np.cos(lat.mean()) * 6371
    dy = (lat[:, None] - lat[None, :]) * 6371
    d = np.hypot(dx, dy)
    np.fill_diagonal(d, np.inf)
    return int(round(np.median(d.min(axis=1)) / 5) * 5)


def event_pairs(events: pd.DataFrame, times: pd.DatetimeIndex, ids: pd.Index) -> dict:
    out = {}
    for kind in KINDS:
        e = events[events.kind == kind]
        t = times.get_indexer(e.time)
        p = ids.get_indexer(e.point_id)
        keep = (t >= 0) & (p >= 0)
        order = np.argsort(t[keep], kind="stable")
        out[kind] = {"t": t[keep][order].tolist(), "p": p[keep][order].tolist()}
    return out


def presets(events: pd.DataFrame, fronts: pd.DataFrame, temp: pd.DataFrame, times: pd.DatetimeIndex) -> list[dict]:
    """A few interesting moments: the largest cold fronts, the widest thunderstorm day, a calm day."""
    # a front needs about 12 h to cross Austria, so show it when most points are in the passage
    flagged = events[events.kind == "cold_front"].groupby("time").point_id.nunique()
    out = []
    for r in fronts[fronts.cold_front].nlargest(3, "share").sort_values("peak_time").itertuples():
        near = flagged[(flagged.index >= r.peak_time - pd.Timedelta("12h")) & (flagged.index <= r.peak_time + pd.Timedelta("12h"))]
        when = near.idxmax() if len(near) else pd.Timestamp(r.peak_time)
        out.append({"kind": "cold_front", "time": f"{when:%Y-%m-%dT%H:00:00Z}", "share": round(float(r.share), 2)})
    storm = events[(events.kind == "thunderstorm") & events.time.dt.month.between(5, 8)]
    if len(storm):
        day = storm.groupby(storm.time.dt.floor("D")).point_id.nunique().idxmax()
        hours = storm[storm.time.dt.floor("D") == day].groupby("time").point_id.nunique()
        out.append({"kind": "thunderstorm", "time": f"{hours.idxmax():%Y-%m-%dT%H:00:00Z}"})
    # calm: a day without any event and the smallest change from the day before
    change = (temp - temp.shift(24)).abs().mean(axis=1).groupby(times.floor("D")).mean().iloc[1:]
    eventful = set(events.time.dt.floor("D"))
    calm = change[[d not in eventful for d in change.index]]
    if len(calm):
        out.append({"kind": "calm", "time": f"{calm.idxmin() + pd.Timedelta(hours=12):%Y-%m-%dT%H:00:00Z}"})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(REPO_DATA / "austria_15km"), help="dataset folder with grid_long.parquet")
    ap.add_argument("--out", default=str(HERE / "site" / "data"), help="output folder for the dashboard data")
    args = ap.parse_args()
    data, out = Path(args.data), Path(args.out)
    (out / "obs").mkdir(parents=True, exist_ok=True)

    print(f"1/3 load {data / 'grid_long.parquet'}")
    points, times, wide = load(data / "grid_long.parquet")
    n, nt = len(points), len(times)
    print(f"  {n} points x {nt} hours")

    print("2/3 write variables")
    total = 0
    for name, spec in VARIABLES.items():
        x = wide[name].to_numpy(np.float32) * spec.get("factor", 1.0)
        first, deltas = encode(quantise(x, spec["lo"], spec["step"], spec.get("sqrt", False)))
        blob = first.tobytes() + deltas.tobytes()
        (out / "obs" / f"{name}.bin").write_bytes(blob)
        total += len(blob)
        print(f"  {name:5s} {len(blob) / 1e6:5.2f} MB")

    print("3/3 write meta and events")
    events = pd.read_parquet(data / "events.parquet")
    fronts = pd.read_csv(data / "fronts.csv", parse_dates=["peak_time"])
    meta = {
        "t0": f"{times[0]:%Y-%m-%dT%H:00:00Z}", "nt": nt, "n": n, "spacing_km": spacing_km(points),
        "id": points.index.tolist(), "lon": points.lon.round(4).tolist(), "lat": points.lat.round(4).tolist(),
        "variables": {k: {x: v for x, v in spec.items() if x != "factor"} for k, spec in VARIABLES.items()},
        "presets": presets(events, fronts, wide["T2M"], times),
        "fronts": [f"{t:%Y-%m-%dT%H:00:00Z}" for t in fronts[fronts.cold_front].peak_time],
    }
    (out / "meta.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    (out / "events.json").write_text(json.dumps(event_pairs(events, times, points.index), separators=(",", ":")),
                                     encoding="utf-8")
    print(f"done: {out}  ({total / 1e6:.1f} MB of observations, spacing {meta['spacing_km']} km)")
    print("view: python -m http.server -d phase1-model-behavior/pair-1/dashboard/site")


if __name__ == "__main__":
    main()
