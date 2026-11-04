"""
Technical smoke test: does TiRex-2 run on our data, and does it react to extra input?

Forecasts hourly 2 m temperature (T2M) at a few random locations of the Austria 5 km
dataset with four input configurations and compares them with two naive baselines:

  a_univariate   only the location's own T2M history
  b_local        + the location's other INCA variables as past covariates
  c_west         + T2M of K locations 30-150 km to the WEST / north-west (usually upstream)
  c_east         + T2M of K locations 30-150 km to the EAST (usually downstream; control)
  persistence    last observed value for every lead time
  seasonal_24h   value 24 h before each target hour

Half of the forecast origins are random, half are "drop" origins where, within the horizon,
it gets >= --drop-k colder than the same hour the day before (the cold-wave proxy from
model-selection.md). The sample is small on purpose: this checks that the pipeline works and gives a
first impression. It is NOT the Phase I analysis.

Usage (inside the container):
  python scripts/tirex_smoke_test.py                       # defaults: 12 points x 8 origins
  python scripts/tirex_smoke_test.py --points 30 --plot    # bigger sample + example figure
  python scripts/tirex_smoke_test.py --covariate-check     # synthetic test: how are covariates used?

Outputs go to data/smoke/ (gitignored): one CSV row per forecast, optional PNG.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch

REPO_DATA = Path(__file__).resolve().parents[1] / "data"
COVARIATES = ["RH2M", "TD2M", "UU", "VV", "P0", "GL", "RR"]
LEADS = [1, 3, 6, 12, 24]


# --------------------------------------------------------------------------- data
def load_points(path: Path) -> pd.DataFrame:
    """One row per lattice point with its projected coordinates (EPSG:31287, metres)."""
    pts = pq.read_table(path, columns=["point_id", "x", "y", "lat", "lon"]).to_pandas()
    return pts.drop_duplicates("point_id").reset_index(drop=True)


def neighbours(pts: pd.DataFrame, pid: int, sector: tuple[float, float], k: int) -> list[int]:
    """K nearest points 30-150 km away whose bearing (seen from pid) lies in `sector`."""
    p = pts.loc[pts.point_id == pid].iloc[0]
    dx, dy = pts.x - p.x, pts.y - p.y
    dist = np.hypot(dx, dy) / 1000
    bearing = (np.rad2deg(np.arctan2(dx, dy)) + 360) % 360
    lo, hi = sector
    ok = (dist >= 30) & (dist <= 150) & (bearing >= lo) & (bearing <= hi)
    return pts.loc[ok].assign(d=dist[ok]).nsmallest(k, "d").point_id.tolist()


def load_series(path: Path, ids: list[int]) -> dict[int, pd.DataFrame]:
    """Hourly series per point. Isolated gaps (a few missing INCA hours, <0.1 %) of up to
    3 h are filled linearly so a 4-week context window isn't discarded for one hour."""
    tab = pq.read_table(path, columns=["point_id", "time", "T2M", *COVARIATES], filters=[("point_id", "in", ids)])
    df = tab.to_pandas()
    return {pid: g.set_index("time").sort_index().drop(columns="point_id").interpolate(limit=3)
            for pid, g in df.groupby("point_id")}


def anomaly_24h(values: np.ndarray, t2m: np.ndarray, origin: int) -> np.ndarray:
    """Forecast/observed T2M minus the observed value 24 h earlier, for each lead time.

    Removes the daily cycle, so a "drop" means colder than the same hour yesterday,
    not just night-time cooling."""
    return values - t2m[origin - 24 : origin - 24 + len(values)]


def pick_origins(t2m: np.ndarray, context: int, horizon: int, n: int, drop_k: float, rng) -> list[tuple[int, str]]:
    """n/2 random origins and n/2 'drop' origins: within the horizon it gets >= drop_k
    colder than the same hour the day before (cold-wave proxy from model-selection.md)."""
    idx = np.arange(context, len(t2m) - horizon)
    future = np.lib.stride_tricks.sliding_window_view(t2m, horizon)[idx]  # t2m[o : o+H]
    past = np.lib.stride_tricks.sliding_window_view(t2m, context)[idx - context]  # t2m[o-C : o]
    yesterday = np.lib.stride_tricks.sliding_window_view(t2m, horizon)[idx - 24]  # t2m[o-24 : o-24+H]
    drop = (future - yesterday).min(axis=1) <= -drop_k
    ok = np.isfinite(future).all(axis=1) & np.isfinite(past).all(axis=1)
    events = rng.permutation(idx[drop & ok])[: n // 2]
    randoms = rng.permutation(idx[~drop & ok])[: n - len(events)]
    return [(int(i), "drop") for i in events] + [(int(i), "random") for i in randoms]


# ------------------------------------------------------------------------- inputs
def zscore(a: np.ndarray) -> np.ndarray:
    """Standardise each covariate with its own context statistics (no look-ahead)."""
    mu, sd = a.mean(axis=1, keepdims=True), a.std(axis=1, keepdims=True)
    return ((a - mu) / np.where(sd > 1e-6, sd, 1)).astype(np.float32)


def build_inputs(series, pid, west, east, origin, context):
    from tirex2 import TimeseriesType

    sl = slice(origin - context, origin)
    own = series[pid]
    target = torch.from_numpy(own.T2M.to_numpy(np.float32)[sl][None].copy())
    local = own[COVARIATES].to_numpy(np.float32)[sl].T
    others = {
        "west": np.stack([series[n].T2M.to_numpy(np.float32)[sl] for n in west]),
        "east": np.stack([series[n].T2M.to_numpy(np.float32)[sl] for n in east]),
    }

    def ts(cov):
        return TimeseriesType(target=target, past_covariates=None if cov is None else torch.from_numpy(zscore(cov)),
                              future_covariates=None)

    return {
        "a_univariate": ts(None),
        "b_local": ts(local),
        "c_west": ts(np.vstack([local, others["west"]])),
        "c_east": ts(np.vstack([local, others["east"]])),
    }


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(REPO_DATA / "austria_5km" / "grid_long.parquet"))
    ap.add_argument("--points", type=int, default=12, help="number of random target locations")
    ap.add_argument("--origins", type=int, default=8, help="forecast origins per location (half 'drop')")
    ap.add_argument("--context", type=int, default=672, help="hours of history (672 = 4 weeks)")
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--neighbours", type=int, default=4, help="K extra locations in c_west / c_east")
    ap.add_argument("--drop-k", type=float, default=8.0, help="K colder than 24 h before that marks a drop origin")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--plot", action="store_true", help="save a figure with example forecasts")
    ap.add_argument("--covariate-check", action="store_true", help="only run the synthetic covariate check and exit")
    args = ap.parse_args()
    if not 1 <= args.horizon <= 24:
        ap.error("--horizon must be 1..24 (the seasonal_24h baseline needs the value 24 h earlier)")

    from tirex2 import load_model

    if args.covariate_check:
        covariate_check(load_model("NX-AI/TiRex-2", device=args.device), seed=args.seed)
        return

    rng = np.random.default_rng(args.seed)
    path = Path(args.data)
    out_dir = REPO_DATA / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/4 choose locations")
    pts = load_points(path)
    targets = []
    for pid in rng.permutation(pts.point_id.to_numpy()):
        west = neighbours(pts, pid, (225, 315), args.neighbours)
        east = neighbours(pts, pid, (45, 135), args.neighbours)
        if len(west) == len(east) == args.neighbours:
            targets.append((int(pid), west, east))
        if len(targets) == args.points:
            break
    ids = sorted({i for pid, w, e in targets for i in (pid, *w, *e)})
    print(f"  {len(targets)} targets, {len(ids)} series to load")

    print("2/4 load series")
    series = load_series(path, ids)
    times = series[targets[0][0]].index

    print(f"3/4 forecast on {args.device}")
    t0 = time.time()
    model = load_model("NX-AI/TiRex-2", device=args.device)
    print(f"  model loaded in {time.time() - t0:.0f}s")
    jobs, inputs = [], {k: [] for k in ["a_univariate", "b_local", "c_west", "c_east"]}
    for pid, west, east in targets:
        t2m = series[pid].T2M.to_numpy(np.float32)
        for origin, kind in pick_origins(t2m, args.context, args.horizon, args.origins, args.drop_k, rng):
            built = build_inputs(series, pid, west, east, origin, args.context)
            if not all(torch.isfinite(v.past_covariates).all() for v in built.values() if v.past_covariates is not None):
                continue  # gap in a covariate or neighbour series
            for k, v in built.items():
                inputs[k].append(v)
            jobs.append((pid, origin, kind))
    preds, secs = {}, {}
    for k, ts in inputs.items():
        t0 = time.time()
        out = model.forecast(ts, prediction_length=args.horizon, output_type="numpy", batch_size=64)
        secs[k] = time.time() - t0
        preds[k] = np.stack([o[0] for o in out])  # (n, 9 quantiles, H)
        print(f"  {k:13s} {len(ts)} forecasts in {secs[k]:.0f}s")

    print("4/4 evaluate")
    rows = []
    for j, (pid, origin, kind) in enumerate(jobs):
        t2m = series[pid].T2M.to_numpy(np.float32)
        truth = t2m[origin : origin + args.horizon]
        base = {
            "persistence": np.full(args.horizon, t2m[origin - 1]),
            "seasonal_24h": t2m[origin - 24 : origin - 24 + args.horizon],
        }
        for k in [*preds, *base]:
            med = preds[k][j, 4] if k in preds else base[k]
            row = {"point_id": pid, "origin": times[origin], "kind": kind, "model": k}
            for h in LEADS:
                row[f"ae_{h}h"] = abs(med[h - 1] - truth[h - 1])
            if k in preds:
                q10, q90 = preds[k][j, 0], preds[k][j, 8]
                row["cover_80"] = float(((truth >= q10) & (truth <= q90)).mean())
            row["pred_drop"] = float(anomaly_24h(med, t2m, origin).min() <= -args.drop_k)
            rows.append(row)
    res = pd.DataFrame(rows)
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
    res.to_csv(out_dir / f"tirex_smoke_{stamp}.csv", index=False)

    order = ["persistence", "seasonal_24h", "a_univariate", "b_local", "c_west", "c_east"]
    pd.set_option("display.width", 140)
    for kind in ["random", "drop"]:
        sub = res[res.kind == kind]
        tab = sub.groupby("model")[[f"ae_{h}h" for h in LEADS] + ["cover_80"]].mean().reindex(order)
        print(f"\nMAE of T2M in K by lead time, {kind} origins (n={sub.point_id.size // len(order)}); "
              "cover_80 = share of truth inside the 10-90 % band (ideal 0.80)")
        print(tab.round(2).to_string())
    hit = res[res.kind == "drop"].groupby("model").pred_drop.mean().reindex(order)
    fa = res[res.kind == "random"].groupby("model").pred_drop.mean().reindex(order)
    print(f"\nPredicted (median) >= {args.drop_k} K colder than 24 h before, within {args.horizon} h: "
          "hit rate on drop origins / false alarms on random origins")
    print(pd.DataFrame({"hit_rate": hit, "false_alarm": fa}).round(2).to_string())
    print(f"\nresults: {out_dir / f'tirex_smoke_{stamp}.csv'}")

    if args.plot:
        plot_examples(jobs, series, preds, args, out_dir / f"tirex_smoke_{stamp}.png")


def covariate_check(model, n: int = 16, context: int = 672, horizon: int = 24, lead: int = 12, seed: int = 0):
    """Synthetic check of HOW TiRex-2 uses covariates (random walks, no real data).

    lead_past    past covariate that runs `lead` hours AHEAD of the target: a perfect early
                 indicator, but only observed up to the forecast origin
    noise_past   pure noise as past covariate (should change nothing)
    known_future the target itself as future covariate (upper bound: future values known)
    """
    from tirex2 import TimeseriesType

    rng = np.random.default_rng(seed)
    err = {k: [] for k in ["univariate", "lead_past", "noise_past", "known_future"]}
    for _ in range(n):
        walk = np.cumsum(rng.normal(0, 1, context + horizon + lead)).astype(np.float32)
        y, truth = walk[: context + horizon], walk[context : context + horizon]
        target = torch.from_numpy(y[None, :context].copy())
        cases = {
            "univariate": (None, None),
            "lead_past": (torch.from_numpy(walk[None, lead : context + lead].copy()), None),
            "noise_past": (torch.randn(1, context), None),
            "known_future": (None, torch.from_numpy(y[None].copy())),
        }
        for k, (past, future) in cases.items():
            q = model.forecast([TimeseriesType(target, past, future)], prediction_length=horizon, output_type="numpy")
            err[k].append(np.abs(q[0][0, 4] - truth))
    print(f"\nCovariate check (synthetic, n={n}): MAE of the median")
    for k, v in err.items():
        v = np.mean(v, axis=0)
        print(f"  {k:13s} lead 1-{lead}h {v[:lead].mean():5.2f}   lead {lead + 1}-{horizon}h {v[lead:].mean():5.2f}")


def plot_examples(jobs, series, preds, args, path: Path, n: int = 4):
    """Sanity figure: a few 'drop' origins with context tail, truth and the 10-90 % band."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    first_drop = {}  # one example per location
    for j, (pid, _, kind) in enumerate(jobs):
        if kind == "drop":
            first_drop.setdefault(pid, j)
    picks = list(first_drop.values())[:n]
    fig, axes = plt.subplots(len(picks), 1, figsize=(9, 2.6 * len(picks)), squeeze=False)
    for ax, j in zip(axes[:, 0], picks):
        pid, origin, _ = jobs[j]
        t2m = series[pid].T2M.to_numpy(np.float32)
        past = np.arange(-72, 0)
        fut = np.arange(args.horizon)
        ax.plot(past, t2m[origin - 72 : origin], color="0.4", lw=1, label="context")
        ax.plot(fut, t2m[origin : origin + args.horizon], color="black", lw=1.5, label="truth")
        for k, color in [("a_univariate", "tab:blue"), ("c_west", "tab:orange")]:
            q = preds[k][j]
            ax.fill_between(fut, q[0], q[8], color=color, alpha=0.2)
            ax.plot(fut, q[4], color=color, lw=1.2, label=k)
        ax.set_title(f"point {pid}, origin {series[pid].index[origin]:%Y-%m-%d %H:%M}", fontsize=9)
        ax.set_ylabel("T2M [°C]")
    axes[0, 0].legend(fontsize=8, ncol=4)
    axes[-1, 0].set_xlabel("hours relative to forecast origin")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    print(f"figure:  {path}")


if __name__ == "__main__":
    main()
