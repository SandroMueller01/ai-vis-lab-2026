"""
Shared event labels for the analysis: cold drops, thunderstorms and cold-wave days, derived
from the hourly INCA temperature (T2M) and precipitation (RR) of an existing dataset build.
Both pairs use these files, so every analysis works with the same events.

Definitions (thresholds are options; defaults from model-selection.md):
  dT24          T2M minus T2M at the same hour the day before (removes the daily cycle)
  dT1           T2M minus T2M one hour before
  cold_drop     dT24 <= -8 K
  thunderstorm  dT1 <= -3 K and RR >= 2 mm in the same hour (proxy, no lightning data)
  cold-wave day UTC day with an hour in which >= 25 % of all locations are in a cold_drop

T2M gaps of up to 3 h are filled linearly per location before differencing; longer gaps
stay NaN and never produce an event. Flagged hours of the same kind and location that are
at most --episode-gap hours apart form one episode.

Outputs, written next to the input (data/<dataset>/):
  events.parquet       one row per flagged location-hour:
                       <id>, time, kind, dT24, dT1, RR, episode
  cold_wave_days.csv   one row per UTC day: peak share of locations in a cold drop at the same
                       hour, that hour (peak_time), cold_wave flag

Usage:
  python data_acquisition/events/build_events.py                       # Austria 5 km
  python data_acquisition/events/build_events.py --data data/tyrol_1km
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DATA = Path(__file__).resolve().parents[2] / "data"
ID_COLUMNS = ["point_id", "cell_id"]  # Austria 5 km, Tyrol 1 km


def load(path: Path) -> tuple[str, pd.DataFrame, pd.DataFrame]:
    """grid_long.parquet -> (id column, T2M, RR) as wide (time x location) frames."""
    import pyarrow.parquet as pq

    names = pq.read_schema(path).names
    id_col = next(c for c in ID_COLUMNS if c in names)
    df = pq.read_table(path, columns=[id_col, "time", "T2M", "RR"]).to_pandas()
    full = pd.date_range(df.time.min(), df.time.max(), freq="1h")
    t2m = df.pivot(index="time", columns=id_col, values="T2M").reindex(full)
    rr = df.pivot(index="time", columns=id_col, values="RR").reindex(full)
    return id_col, t2m, rr


def fill_short_gaps(t2m: pd.DataFrame, max_gap: int) -> pd.DataFrame:
    """Linear fill of NaN runs of at most max_gap hours; longer runs stay NaN entirely.
    (pandas' interpolate(limit=...) would also fill the first hours of a long gap.)"""
    na = t2m.isna().to_numpy()
    fwd, bwd = np.zeros(na.shape, dtype=np.int32), np.zeros(na.shape, dtype=np.int32)
    for i in range(len(na)):
        fwd[i] = (fwd[i - 1] + 1 if i else 1) * na[i]
    for i in range(len(na) - 1, -1, -1):
        bwd[i] = (bwd[i + 1] + 1 if i < len(na) - 1 else 1) * na[i]
    filled = t2m.interpolate(limit_area="inside")
    return filled.mask(na & (fwd + bwd - 1 > max_gap))


def deltas(t2m: pd.DataFrame, max_gap: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """dT24 and dT1 per location, after filling T2M gaps of up to max_gap hours."""
    t = fill_short_gaps(t2m, max_gap)
    return t - t.shift(24), t - t.shift(1)


def flags(dt24, dt1, rr, cold_k=8.0, storm_k=3.0, storm_rr=2.0) -> dict[str, pd.DataFrame]:
    """Boolean (time x location) masks; NaN never counts as an event."""
    return {"cold_drop": dt24 <= -cold_k, "thunderstorm": (dt1 <= -storm_k) & (rr >= storm_rr)}


def episodes(mask: pd.DataFrame, gap: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flagged cells as (time index, location index, episode id). Hours of one location
    that are at most `gap` hours apart share an episode id (ids are unique overall)."""
    loc, ti = np.nonzero(mask.to_numpy().T)  # sorted by location, then time
    new = np.ones(len(ti), dtype=bool)
    new[1:] = (loc[1:] != loc[:-1]) | (np.diff(ti) > gap)
    return ti, loc, np.cumsum(new) - 1


def cold_wave_days(cold: pd.DataFrame, valid: pd.DataFrame, share: float = 0.25) -> pd.DataFrame:
    """Per UTC day: the largest share of locations in a cold drop at the SAME hour, and that hour."""
    hourly = cold.sum(axis=1) / valid.sum(axis=1).clip(lower=1)
    by_day = hourly.groupby(hourly.index.floor("D"))
    out = pd.DataFrame({"share": by_day.max(), "peak_time": by_day.idxmax()})
    out["cold_wave"] = out.share >= share
    out.index = out.index.date
    out.index.name = "date"
    return out


def build(id_col, t2m, rr, args) -> tuple[pd.DataFrame, pd.DataFrame]:
    dt24, dt1 = deltas(t2m, args.max_gap)
    masks = flags(dt24, dt1, rr, args.cold_k, args.storm_k, args.storm_rr)
    frames, offset = [], 0
    for kind, mask in masks.items():
        ti, loc, ep = episodes(mask, args.episode_gap)
        frames.append(pd.DataFrame({
            id_col: mask.columns.to_numpy()[loc], "time": mask.index[ti], "kind": kind,
            "dT24": dt24.to_numpy()[ti, loc].astype("float32"), "dT1": dt1.to_numpy()[ti, loc].astype("float32"),
            "RR": rr.to_numpy()[ti, loc].astype("float32"), "episode": (ep + offset).astype("int32")}))
        offset += int(ep.max()) + 1 if len(ep) else 0
    events = pd.concat(frames, ignore_index=True)
    events["kind"] = events.kind.astype("category")
    days = cold_wave_days(masks["cold_drop"], dt24.notna(), args.cold_share)
    return events, days


def summary(events: pd.DataFrame, days: pd.DataFrame, id_col: str, n_loc: int, n_hours: int):
    years = n_hours / 8760
    for kind, g in events.groupby("kind", observed=True):
        per_loc = g.groupby(id_col).episode.nunique()
        months = g.drop_duplicates("episode").time.dt.month
        print(f"  {kind:12s} {len(g):9,d} hours, {g.episode.nunique():7,d} episodes, "
              f"{g.episode.nunique() / n_loc / years:5.1f} per location and year "
              f"(median {per_loc.median() / years:.0f} where any), {months.between(5, 8).mean() * 100:3.0f} % in May-Aug")
    cw = days[days.cold_wave]
    print(f"  cold-wave days: {len(cw)} (largest: "
          + ", ".join(f"{d} {s * 100:.0f} %" for d, s in cw.share.nlargest(3).items()) + ")")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(REPO_DATA / "austria_5km"), help="dataset folder with grid_long.parquet")
    ap.add_argument("--cold-k", type=float, default=8.0, help="cold drop: K colder than 24 h before")
    ap.add_argument("--storm-k", type=float, default=3.0, help="thunderstorm: K drop within 1 h")
    ap.add_argument("--storm-rr", type=float, default=2.0, help="thunderstorm: mm rain in that hour")
    ap.add_argument("--cold-share", type=float, default=0.25, help="cold-wave day: share of locations")
    ap.add_argument("--max-gap", type=int, default=3, help="fill T2M gaps up to this many hours")
    ap.add_argument("--episode-gap", type=int, default=6, help="merge flagged hours up to this far apart")
    args = ap.parse_args()

    data = Path(args.data)
    print(f"1/3 load {data / 'grid_long.parquet'}")
    id_col, t2m, rr = load(data / "grid_long.parquet")
    print(f"  {t2m.shape[1]} locations x {len(t2m)} hours")

    print("2/3 label events")
    events, days = build(id_col, t2m, rr, args)

    print("3/3 write")
    events.to_parquet(data / "events.parquet", index=False, compression="zstd")
    days.to_csv(data / "cold_wave_days.csv")
    summary(events, days, id_col, t2m.shape[1], len(t2m))
    print(f"files: {data / 'events.parquet'}, {data / 'cold_wave_days.csv'}")


if __name__ == "__main__":
    main()
