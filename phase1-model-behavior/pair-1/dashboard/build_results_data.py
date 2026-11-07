"""
Data for the question pages of the Phase I dashboard (site/q1.html ... q5.html), computed from the TiRex-2
forecasts of run_forecasts.py and the Austria 15 km dataset with its event labels.

Written to site/data/:
  results.json         all numbers behind the charts: error by hours ahead, situations, events, cold-front
                       candidates (with arrival times and time-longitude grids), error around the front arrival,
                       maps, neighbours, start times
  forecast_runs.json   the forecast runs that can be shown in detail (cold fronts, a calm day, a thunderstorm day, normal days)
  forecast_runs.bin    their context, measured values and quantiles, int16 in tenths of a degree, layout per run and
                       point: 36 h context, 24 h measured, 24 h each of q10, q50 and q90

Definitions (same as in the figures of the answers):
  wrong        |forecast median - measured| > 2 K
  in the band  measured value between the 10 % and the 90 % quantile of the forecast
  situations   weather change = |measured - measured 24 h before| in the forecast hour; rain = at least 1 mm in the
               12 h; day = global radiation above 50 W/m2; the event rows use all forecasts including the extra front runs
  front error  mean forecast - measured, by hours since the front reached each point (first passage hour within
               12 h of the peak), forecasts 1-24 h ahead

Usage:
  python phase1-model-behavior/pair-1/dashboard/build_results_data.py
  python phase1-model-behavior/pair-1/dashboard/build_results_data.py --forecasts data/austria_15km/tirex2_forecasts.npz
Data: GeoSphere Austria, https://data.hub.geosphere.at (CC BY 4.0).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "data_acquisition" / "events"))
from build_events import fronts, load, passages  # shared definitions of the event labels

H = 24
CTX = 36  # hours of context stored for the detail view
SCALE = 10  # stored values are tenths of a degree
RELS = np.arange(-12, 13)
PLACES = {
    "Vienna": (48.21, 16.37), "Linz": (48.31, 14.29), "Salzburg": (47.81, 13.04), "Graz": (47.07, 15.44),
    "Klagenfurt": (46.62, 14.31), "Innsbruck": (47.27, 11.39), "Bregenz": (47.50, 9.75),
}
# fronts must reach this share of the points, and fit a moving line (see data_acquisition/events/README.md)
MIN_R2, SPEED_RANGE, DIRECTION_RANGE = 0.3, (1.0, 30.0), (60.0, 240.0)


# ---------------------------------------------------------------------------------------------------- helpers
def neighbour_counts(x: np.ndarray, y: np.ndarray, step: float) -> np.ndarray:
    """Number of direct neighbours (left, right, above, below) of each point on a lattice with the given step."""
    have = set(zip(x.tolist(), y.tolist()))
    offsets = [(step, 0), (-step, 0), (0, step), (0, -step)]
    return np.array([sum((a + dx, b + dy) in have for dx, dy in offsets) for a, b in zip(x.tolist(), y.tolist())])


def pack_runs(context, truth, q10, q50, q90) -> np.ndarray:
    """Arrays (runs, points, hours) -> int16 (runs, points, 36 + 24 + 3 * 24) in tenths of a degree."""
    both = np.concatenate([context, truth, q10, q50, q90], axis=2)
    return np.round(both * SCALE).astype("<i2")


def unpack_runs(packed: np.ndarray):
    """Inverse of pack_runs (what the browser does)."""
    v = packed.astype(np.float32) / SCALE
    return v[..., :CTX], v[..., CTX : CTX + H], v[..., CTX + H : CTX + 2 * H], v[..., CTX + 2 * H : CTX + 3 * H], v[..., CTX + 3 * H :]


def why_not(row) -> str:
    """Plain-words reason why a candidate is not counted as a cold front."""
    reasons = []
    if row.r2 < MIN_R2:
        reasons.append(f"the passage times do not form a moving line (R² {row.r2:.2f}, needs {MIN_R2})")
    if not SPEED_RANGE[0] <= row.speed_ms <= SPEED_RANGE[1]:
        reasons.append(f"a speed of {row.speed_ms * 3.6:.0f} km/h is not realistic for a front")
    if not DIRECTION_RANGE[0] <= row.moves_to_deg <= DIRECTION_RANGE[1]:
        reasons.append(f"it moves towards {row.moves_to_deg:.0f}°, not from the west or north")
    return "; ".join(reasons) if reasons else "a moving line from the west or north"


def r1(a):
    return np.round(np.asarray(a, dtype=float), 1).tolist()


def r2(a):
    return np.round(np.asarray(a, dtype=float), 2).tolist()


def r3(a):
    return np.round(np.asarray(a, dtype=float), 3).tolist()


# ---------------------------------------------------------------------------------------------------- inputs
def read_inputs(data: Path, forecasts: Path):
    f = np.load(forecasts, allow_pickle=True)
    _, wide, xy = load(data / "grid_long.parquet")
    pids = wide["T2M"].columns.to_numpy()
    if not np.array_equal(pids, f["pids"]):
        raise SystemExit("the forecast file and the dataset have different points")
    g = pd.read_parquet(data / "grid_long.parquet", columns=["point_id", "time", "x", "y", "lat", "lon", "VV", "GL", "wind_speed"])
    pts = g.drop_duplicates("point_id").set_index("point_id").loc[pids, ["x", "y", "lat", "lon"]]
    times = wide["T2M"].index

    def grid(name):
        return g.pivot(index="time", columns="point_id", values=name).reindex(times)[pids].to_numpy(np.float32)

    inputs = {
        "T": wide["T2M"].interpolate(limit_area="inside").ffill().bfill().to_numpy(np.float32),  # as given to the model
        "RR": wide["RR"].to_numpy(np.float32),
        "P": (wide["P0"].interpolate(limit=3, limit_area="inside") / 100).to_numpy(np.float32),  # hPa
        "VV": grid("VV"), "GL": grid("GL"), "WS": grid("wind_speed"),
    }
    events = pd.read_parquet(data / "events.parquet")
    return f, wide, xy, pts, times, pids, inputs, events


def event_masks(events: pd.DataFrame, times, pids) -> dict:
    out = {}
    for kind in ("cold_front", "cold_drop", "thunderstorm"):
        m = np.zeros((len(times), len(pids)), bool)
        e = events[events.kind == kind]
        m[times.get_indexer(e.time), pd.Index(pids).get_indexer(e.point_id)] = True
        out[kind] = m
    return out


# ---------------------------------------------------------------------------------------------------- fronts
def front_candidates(wide, xy):
    """Candidate fronts as labelled by events/build_events.py, and the hours in which a passage starts (time x point)."""
    passage = passages(wide["T2M"], wide["P0"])
    cand, _ = fronts(passage, xy)
    onset = (passage & ~passage.shift(1, fill_value=False)).to_numpy()
    return cand, onset


def arrival(onset: np.ndarray, i: int, half: int = 12) -> np.ndarray:
    """First passage hour within +-half hours of the peak index i, per point; -1 if there is none."""
    win = onset[i - half : i + half]
    return np.where(win.any(0), i - half + win.argmax(0), -1)


def time_longitude(anom: np.ndarray, lon: np.ndarray, i: int, edges: np.ndarray) -> np.ndarray:
    """(36 hours around the peak, longitude strips) mean 3 h temperature change compared with normal."""
    b = np.digitize(lon, edges) - 1
    z = np.full((36, len(edges) - 1), np.nan)
    for k in range(len(edges) - 1):
        sel = b == k
        if sel.any():
            z[:, k] = np.nanmean(anom[i - 18 : i + 18][:, sel], axis=1)
    return z


# ---------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(REPO / "data" / "austria_15km"), help="Austria 15 km dataset with event labels")
    ap.add_argument("--forecasts", default=None, help="output of run_forecasts.py (default: <data>/tirex2_forecasts.npz)")
    ap.add_argument("--out", default=str(HERE / "site" / "data"), help="output folder")
    args = ap.parse_args()
    data, out = Path(args.data), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("1/5 load")
    f, wide, xy, pts, times, pids, inp, events = read_inputs(data, Path(args.forecasts or data / "tirex2_forecasts.npz"))
    T, RR, Pr, VV, GL, WS = (inp[k] for k in ("T", "RR", "P", "VV", "GL", "WS"))
    P, oi, tags = f["preds"].astype(np.float32), f["origin_idx"], f["tags"]
    n_run, n_pt = P.shape[:2]
    G = tags == "grid"
    masks = event_masks(events, times, pids)
    lon, lat = pts.lon.to_numpy(), pts.lat.to_numpy()

    tidx = oi[:, None] + np.arange(H)[None, :]
    truth = T[tidx].transpose(0, 2, 1)  # (runs, points, hours)
    last_hour = np.repeat(T[oi - 1][:, :, None], H, axis=2)
    yesterday = T[tidx - 24].transpose(0, 2, 1)
    q10, med, q90 = P[:, :, 0], P[:, :, 4], P[:, :, 8]
    err = med - truth
    ae = np.abs(err)
    inband = (truth >= q10) & (truth <= q90)
    leads = np.arange(1, H + 1)

    print("2/5 error by hours ahead, situations, events")
    forecasters = {"tirex": med, "last_hour": last_hour, "yesterday": yesterday}
    lead = {"leads": leads.tolist(), "mae": {}, "wrong": {}}
    for name, fc in forecasters.items():
        e = np.abs(fc[G] - truth[G])
        lead["mae"][name] = r3(e.mean(axis=(0, 1)))
        lead["wrong"][name] = r1((e > 2).mean(axis=(0, 1)) * 100)
    lead["cover"] = r1(inband[G].mean(axis=(0, 1)) * 100)
    lead["improvement"] = r1((1 - np.array(lead["mae"]["tirex"]) / np.array(lead["mae"]["yesterday"])) * 100)

    ix = tidx[:, :12]
    sl = slice(0, 12)
    a, w, t12, y12 = ae[..., sl], inband[..., sl], truth[..., sl], yesterday[..., sl]
    change = np.abs(t12 - y12)
    rain = np.broadcast_to((RR[ix].sum(axis=1) >= 1)[:, :, None], a.shape)
    sun = GL[ix].transpose(0, 2, 1) > 50
    wind = WS[ix].transpose(0, 2, 1)
    month = np.broadcast_to(times[oi].month.to_numpy()[:, None, None], a.shape)
    spread = np.broadcast_to(G[:, None, None], a.shape)
    ev12 = {k: m[ix].transpose(0, 2, 1) for k, m in masks.items()}
    rows = [
        ("Weather change", "like yesterday (less than 2 °C different)", (change < 2) & spread),
        ("Weather change", "2 to 5 °C different from yesterday", (change >= 2) & (change < 5) & spread),
        ("Weather change", "5 °C or more different from yesterday", (change >= 5) & spread),
        ("Time of day", "daytime", sun & spread), ("Time of day", "night", ~sun & spread),
        ("Rain", "dry (less than 1 mm in 12 h)", ~rain & spread), ("Rain", "rainy (1 mm or more in 12 h)", rain & spread),
        ("Wind", "calm (less than 2 m/s)", (wind < 2) & spread), ("Wind", "windy (5 m/s or more)", (wind >= 5) & spread),
        ("Season", "winter", np.isin(month, [12, 1, 2]) & spread), ("Season", "spring", np.isin(month, [3, 4, 5]) & spread),
        ("Season", "summer", np.isin(month, [6, 7, 8]) & spread), ("Season", "autumn", np.isin(month, [9, 10, 11]) & spread),
        ("Weather events", "during a cold front", ev12["cold_front"]), ("Weather events", "during a cold drop", ev12["cold_drop"]),
        ("Weather events", "during a thunderstorm", ev12["thunderstorm"]),
    ]
    situations = [
        {"group": g_, "label": lab, "wrong": float(round((a[m] > 2).mean() * 100, 1)),
         "cover": float(round(w[m].mean() * 100, 1)), "n": int(m.any(axis=2).sum())}
        for g_, lab, m in rows
    ]

    lead_events = {"leads": leads.tolist(), "all": lead["mae"]["tirex"], "n": {}}
    tm = {k: m[tidx].transpose(0, 2, 1) for k, m in masks.items()}
    for k, m in tm.items():
        lead_events[k] = r3((ae * m).sum(axis=(0, 1)) / np.maximum(m.sum(axis=(0, 1)), 1))
        lead_events["n"][k] = int(m.sum())

    big = a > 2
    warm = err[..., sl] > 0
    mistake_rows = [("all situations", spread), ("daytime", sun & spread), ("night", ~sun & spread),
                    ("during a cold front", ev12["cold_front"]), ("during a cold drop", ev12["cold_drop"]),
                    ("during a thunderstorm", ev12["thunderstorm"])]
    mistakes = [{"label": lab, "too_warm": float(round((big & warm & m).sum() / max((big & m).sum(), 1) * 100, 1)),
                 "n_wrong": int((big & m).sum())} for lab, m in mistake_rows]
    summary = {
        "n_points": int(n_pt), "n_runs": int(n_run), "n_spread": int(G.sum()), "n_front_runs": int((~G).sum()),
        "wrong12": float(np.mean(lead["wrong"]["tirex"][:12])), "wrong24": float(np.mean(lead["wrong"]["tirex"][12:])),
        "mae12": float(np.mean(lead["mae"]["tirex"][:12])), "mae24": float(np.mean(lead["mae"]["tirex"][12:])),
        "cover": float(inband[G].mean() * 100), "improve1": lead["improvement"][0], "improve12": lead["improvement"][11],
        "improve24": lead["improvement"][23],
    }

    print("3/5 cold fronts")
    cand, onset = front_candidates(wide, xy)
    anom_in = pd.DataFrame(T - np.vstack([np.full((3, n_pt), np.nan), T[:-3]]), index=times)
    anom = (anom_in - anom_in.groupby([anom_in.index.month, anom_in.index.hour]).transform("mean")).to_numpy()
    edges = np.arange(9.4, 17.4, 0.25)
    listed, composite = [], []
    for _, row in cand.iterrows():
        i = times.get_loc(row.peak_time)
        arr = arrival(onset, i)
        has = arr >= 0
        rel = np.where(has, arr - np.median(arr[has]) if has.any() else 0, 99)
        listed.append({
            "peak": f"{row.peak_time:%Y-%m-%dT%H:00:00Z}", "share": float(round(row.share, 3)), "r2": float(round(row.r2, 3)),
            "speed_kmh": float(round(row.speed_ms * 3.6, 1)), "direction": float(round(row.moves_to_deg)), "accepted": bool(row.cold_front),
            "why": why_not(row), "arrival": np.where(has, np.round(rel), 99).astype(int).tolist(),
            "z": np.round(np.nan_to_num(time_longitude(anom, lon, i, edges), nan=99), 1).tolist(),
        })
        if row.cold_front:
            composite.extend((arr[j], j) for j in np.where(has)[0] if 12 <= arr[j] < len(times) - 12)
    ti, pj = np.array(composite).T
    idx = ti[:, None] + RELS[None, :]
    front_check = {
        "rel": RELS.tolist(), "n": len(ti),
        "dT": r2(np.nanmean(T[idx, pj[:, None]] - T[ti - 12, pj][:, None], 0)),
        "dP": r2(np.nanmean(Pr[idx, pj[:, None]] - Pr[ti - 12, pj][:, None], 0)),
        "v": r2(np.nanmean(VV[idx, pj[:, None]], 0)),
        "rain": r1(np.nanmean((RR[idx, pj[:, None]] >= 0.5), 0) * 100),
        "base_v": float(round(np.nanmean(VV), 2)), "base_rain": float(round((RR >= 0.5).mean() * 100, 1)),
    }

    print("4/5 error around the front, maps, neighbours, start times")
    # the front runs started 12 h and 6 h before the peak of an accepted front (the first front is too early for the history)
    by_origin = {times.get_loc(p) - lead_before: p for p in cand[cand.cold_front].peak_time for lead_before in (12, 6)}
    run_front = [by_origin[oi[k]] for k in np.where(~G)[0]]
    s_err = [[] for _ in RELS]
    s_in = [[] for _ in RELS]
    for p, k in zip(run_front, np.where(~G)[0]):
        arr = arrival(onset, times.get_loc(p))
        for j in np.where(arr >= 0)[0]:
            for hh in range(H):
                r_ = oi[k] + hh - arr[j]
                if -12 <= r_ <= 12:
                    s_err[r_ + 12].append(err[k, j, hh])
                    s_in[r_ + 12].append(inband[k, j, hh])
    front_error = {
        "rel": RELS.tolist(), "mean": r2([np.mean(x) for x in s_err]), "q25": r2([np.percentile(x, 25) for x in s_err]),
        "q75": r2([np.percentile(x, 75) for x in s_err]), "cover": r1([np.mean(x) * 100 for x in s_in]),
        "n": [len(x) for x in s_err], "runs": int((~G).sum()), "fronts": len(set(run_front)),
    }

    mae_pt = ae[G][..., sl].mean(axis=(0, 2))
    bias_pt = err[G][..., sl].mean(axis=(0, 2))
    nb = neighbour_counts(pts.x.to_numpy(), pts.y.to_numpy(), 15000)
    region = np.digitize(pts.x.to_numpy(), [300000, 500000])
    regions = ["West (Vorarlberg, Tyrol)", "Centre (Salzburg, Carinthia, Styria)", "East (Upper and Lower Austria, Vienna, Burgenland)"]
    points = {
        "id": pids.tolist(), "lon": r3(lon), "lat": r3(lat), "mae12": r3(mae_pt), "bias12": r3(bias_pt),
        "neighbours": nb.tolist(), "region": region.tolist(),
    }
    neighbour_stats = [{"neighbours": int(k), "n": int((nb == k).sum()), "mae": float(round(mae_pt[nb == k].mean(), 3))}
                       for k in sorted(set(nb.tolist()))]
    region_stats = [{"name": regions[k], "n": int((region == k).sum()), "mae": float(round(mae_pt[region == k].mean(), 3)),
                     "bias": float(round(bias_pt[region == k].mean(), 3))} for k in range(3)]
    hrs = times[oi[G]].hour.to_numpy()
    starts = sorted(set(hrs.tolist()))
    start_heat = {"hours": starts, "leads": leads.tolist(), "mae": [r3(ae[G][hrs == h_].mean(axis=(0, 1))) for h_ in starts]}
    start_heat["n"] = [int((hrs == h_).sum()) for h_ in starts]

    print("5/5 forecast runs for the detail view")
    chosen = []  # (run index, label, kind, front peak)
    for k, p in zip(np.where(~G)[0], run_front):
        lead_before = 12 if tags[k] == "front-12" else 6
        chosen.append((int(k), f"Cold front {p:%d %b %Y} · start {lead_before} h before the peak", "front", p))
    spread_idx = np.where(G)[0]
    quiet, storm = [], []
    for k in spread_idx:
        w_ = slice(oi[k], oi[k] + H)
        events_in = masks["cold_front"][w_].any() or masks["cold_drop"][w_].any() or masks["thunderstorm"][w_].any()
        quiet.append(np.abs(truth[k] - yesterday[k]).mean() if not events_in else np.inf)
        storm.append(masks["thunderstorm"][w_].sum())
    calm_k, storm_k = int(spread_idx[int(np.argmin(quiet))]), int(spread_idx[int(np.argmax(storm))])
    chosen.append((calm_k, f"Calm day · start {times[oi[calm_k]]:%d %b %Y %H:%M} UTC", "calm", None))
    chosen.append((storm_k, f"Thunderstorm day · start {times[oi[storm_k]]:%d %b %Y %H:%M} UTC", "storm", None))
    noon = [k for k in spread_idx if times[oi[k]].hour == 12 and k not in (calm_k, storm_k)]
    for k in noon[2::6][:6]:
        chosen.append((int(k), f"Normal day · start {times[oi[k]]:%d %b %Y %H:%M} UTC", "normal", None))
    ks = [c[0] for c in chosen]
    ctx = np.stack([T[oi[k] - CTX : oi[k]].T for k in ks])
    packed = pack_runs(ctx, truth[ks], q10[ks], med[ks], q90[ks])
    (out / "forecast_runs.bin").write_bytes(packed.tobytes())
    run_meta = []
    for k, label, kind, p in chosen:
        item = {"label": label, "kind": kind, "start": f"{times[oi[k]]:%Y-%m-%dT%H:00:00Z}"}
        if p is not None:
            arr = arrival(onset, times.get_loc(p))
            item["arrival"] = np.where(arr >= 0, arr - oi[k], 99).astype(int).tolist()
            item["peak"] = f"{p:%Y-%m-%dT%H:00:00Z}"
        run_meta.append(item)
    near = {name: int(np.argmin((lat - la) ** 2 + ((lon - lo) * 0.68) ** 2)) for name, (la, lo) in PLACES.items()}
    (out / "forecast_runs.json").write_text(json.dumps({
        "n": int(n_pt), "stride": CTX + 4 * H, "ctx": CTX, "h": H, "scale": SCALE, "runs": run_meta, "places": near,
    }, separators=(",", ":")), encoding="utf-8")

    results = {
        "summary": summary, "lead": lead, "lead_events": lead_events, "situations": situations, "mistakes": mistakes,
        "fronts": listed, "front_check": front_check, "front_error": front_error, "points": points,
        "regions": region_stats, "neighbour_stats": neighbour_stats, "start_heat": start_heat,
        "lon_edges": np.round(edges, 2).tolist(), "time_rows": list(range(-18, 18)),
    }
    (out / "results.json").write_text(json.dumps(results, separators=(",", ":")), encoding="utf-8")
    print(f"done: {out}  (results.json {(out / 'results.json').stat().st_size / 1e3:.0f} kB, "
          f"forecast_runs.bin {(out / 'forecast_runs.bin').stat().st_size / 1e6:.1f} MB, {len(run_meta)} runs)")


if __name__ == "__main__":
    main()
