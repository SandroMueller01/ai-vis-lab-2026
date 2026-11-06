"""
Data for Carlos's part of the Phase I dashboard, computed from the saved forecasts of his experiment notebooks
(phase1-model-behavior/pair-1/experiments/) and the Austria 15 km dataset. No model runs: everything is read from
the saved results and reduced to what each chart shows.

Written to site/data/carlos/ (one small JSON file per chart, so a page only loads what it needs):
  front_explorer.json   Exp 3: every point of every cold front (setup A, start 6 h before the drop): unusual drop
                        captured (0-100 %) and the change since the forecast start (what happened and forecast median)
  catching_up.json      Exp 3 section 6: the average front seen from five forecast starts (-6, 0, +3, +6, +12 h)
  band_honesty.json     Exp 11: share of forecast hours below / inside / above the 10-90 % band
  time_curve.json       Exp 7 step 1: time curve of the whole map of Austria (classical MDS) and three snapshot maps
  fixed_sundays.json    Exp 1: scores (repeated vs one-off Sundays), score vs size of change, one copy and one ignore case
  weird_history.json    Exp 6: band width vs inserted drops (4-16), and the 61 real forecasts of the slider example
  drop_position.json    Exp 6: one drop of 8 °C moved through the history (all cases every 2 days, the example every hour)
  where_it_looks.json   Exp 10: occlusion folded into days (normal days and cold fronts) and the 32-hour pattern
  cold_lasts.json       Exp 5: does the model expect the cold to last? (forecasts started +6 to +48 h after the drop)

Definitions (same as in the notebooks):
  unusual        value minus the usual value for that point, month and hour (mean over the year of data)
  drop captured  forecast drop / real drop in the drop window (drop start and the 6 h after it), capped to 0-100 %;
                 the unusual version uses the unusual values, so normal evening cooling does not count
  score (Exp 1)  share of the way the forecast median moved towards the fixed Sunday value, mean over the 24 h

Usage:
  python phase1-model-behavior/pair-1/dashboard/build_carlos_data.py
  python phase1-model-behavior/pair-1/dashboard/build_carlos_data.py --results data/notebooks/results
Data: GeoSphere Austria, https://data.hub.geosphere.at (CC BY 4.0).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
H = 24
BEFORE = 6  # forecast starts 6 h before the drop (Exp 3)
W = slice(BEFORE, BEFORE + 7)  # drop window: drop start and the 6 h after it


def r1(a):
    """Round to 0.1 for the JSON (keeps the files small); NaN -> None."""
    a = np.round(np.asarray(a, dtype=float), 1)
    return np.where(np.isfinite(a), a, None).tolist()


def r0(a):
    a = np.round(np.asarray(a, dtype=float))
    return np.where(np.isfinite(a), a, None).tolist()


# ---------------------------------------------------------------------------------------------------- inputs
class Grid:
    """Hourly temperature of all points (as in the notebooks) and its usual value per point, month and hour."""

    def __init__(self, data: Path):
        df = pd.read_parquet(data / "grid_long.parquet", columns=["point_id", "time", "T2M"])
        tw = df.pivot(index="time", columns="point_id", values="T2M").interpolate(limit=3, limit_area="inside")
        self.times, self.pids = tw.index, tw.columns
        self.T = tw.to_numpy(np.float32)
        self.usual = pd.DataFrame(self.T).groupby([self.times.month, self.times.hour]).transform("mean").to_numpy(np.float32)
        self.col = {p: i for i, p in enumerate(self.pids)}
        pts = pd.read_csv(data / "points_with_labels.csv").set_index("point_id").loc[self.pids]
        self.lon, self.lat = pts.lon.to_numpy(), pts.lat.to_numpy()

    def idx(self, iso):
        t = pd.Timestamp(iso)
        if self.times.tz is not None and t.tz is None:
            t = t.tz_localize(self.times.tz)
        return self.times.get_loc(t)


def drop_in(y):
    return y[:, BEFORE] - y[:, W].min(axis=1)


# ---------------------------------------------------------------------------------------------------- charts
def front_explorer(res: Path, g: Grid):
    z = np.load(res / "exp3_all_points_A.npz")
    o = np.array([g.idx(s) for s in z["start"]])
    c = np.array([g.col[p] for p in z["point_id"]])
    truth, med = z["truth"], z["forecast"][:, 4]
    us = np.stack([g.usual[i : i + H, j] for i, j in zip(o, c)])
    last = g.T[o - 1, c][:, None]  # last known hour
    rd_u = drop_in(truth - us)
    cap = np.where(rd_u >= 2, 100 * np.clip(drop_in(med - us) / np.where(rd_u >= 2, rd_u, 1), 0, 1), np.nan)
    fronts = sorted(set(z["front"]))
    doubtful = {"2026-07-03", "2026-09-14"}  # almost no drop at the anchor hour (weak labels)
    out = {"hours": list(range(-BEFORE, H - BEFORE)), "drop_window": [0, 6],
           "points": {"id": z_list(g.pids), "lon": r3(g.lon), "lat": r3(g.lat)}, "fronts": []}
    for f in fronts:
        m = z["front"] == f
        day = f[:10]
        out["fronts"].append({
            "front": f, "day": day, "doubtful": day in doubtful, "n": int(m.sum()),
            "captured_mean": round(float(np.nanmean(cap[m])), 1), "unusual_drop_median": round(float(np.nanmedian(rd_u[m])), 1),
            "point": z_list(z["point_id"][m]), "captured": r0(cap[m]), "unusual_drop": r1(rd_u[m]),
            "truth": r1(truth[m] - last[m]), "forecast": r1(med[m] - last[m]),
        })
    return out


def catching_up(res: Path):
    z = np.load(res / "exp3_inside_front_30perfront.npz")
    rel, tw = z["rel_hours"], z["truth"]
    ref = tw[:, np.searchsorted(rel, 0)][:, None]  # temperature when the drop starts
    span = (rel >= -12) & (rel < 12 + H)
    starts = []
    for off in [-6, 0, 3, 6, 12]:
        f = z[f"start{off:+d}"]
        lo, mid, hi = ((f[:, q] - ref).mean(axis=0) for q in (0, 4, 8))
        starts.append({"start": off, "hours": list(range(off, off + H)), "q10": r1(lo), "q50": r1(mid), "q90": r1(hi)})
    return {"n": len(tw), "truth": {"hours": rel[span].tolist(), "mean": r1((tw - ref).mean(axis=0)[span])}, "starts": starts}


def band_honesty(res: Path):
    z2, z3, z5 = (np.load(res / f) for f in ["exp2_forecasts_50x48.npz", "exp3_forecasts_30perfront.npz", "exp5_after_front.npz"])
    ok = (z3["truth"][:, 6] - z3["truth"][:, 6:13].min(1)) >= 2
    groups = {"normal days": [(z2["w4"], z2["truth"])],
              "a front coming": [(z3["A"][ok], z3["truth"][ok])],
              "just after the drop": [(z5["fc +6 h"], z5["truth +6 h"]), (z5["fc +12 h"], z5["truth +12 h"])]}
    rows = []
    for name, parts in groups.items():
        b = np.bincount(np.concatenate([(t[:, None, :] > f).sum(axis=1).ravel() for f, t in parts]), minlength=10)
        s = 100 * b / b.sum()
        rows.append({"group": name, "hours": int(b.sum()), "below": round(s[0], 1), "inside": round(s[1:9].sum(), 1), "above": round(s[9], 1)})
    return {"honest": {"below": 10, "inside": 80, "above": 10}, "rows": rows}


def mds(x):
    """Classical MDS (as in the Exp 7 notebook): 2D positions whose distances best match those between the rows of x."""
    sq = (x**2).sum(1)
    d2 = np.maximum(sq[:, None] + sq[None] - 2 * x @ x.T, 0)
    n = len(x)
    j = np.eye(n) - 1 / n
    w, v = np.linalg.eigh(-0.5 * j @ d2 @ j)
    i = np.argsort(w)[::-1][:2]
    return v[:, i] * np.sqrt(np.maximum(w[i], 0)), w[i].sum() / w[w > 0].sum()


def time_curve(res: Path, data: Path, g: Grid):
    z = np.load(res / "exp7_time_curves_378pts_1h.npz")
    tt = pd.DatetimeIndex(pd.to_datetime(z["times"]))
    r = (z["truth"] - z["usual"]).astype(float)  # (120 hours, 378 points)
    xy, kept = mds(r)
    ev = pd.read_parquet(data / "events.parquet")
    ev = ev[ev.kind == "cold_front"]
    peak = pd.Timestamp("2026-03-25 22:00", tz=g.times.tz)  # as in the notebook: passages within a day of the peak
    in_front = ev[(ev.time >= peak - pd.Timedelta("1D")) & (ev.time <= peak + pd.Timedelta("1D"))].groupby("time").point_id.nunique()
    share = (in_front.reindex(tt).fillna(0) / r.shape[1]).to_numpy()
    ip = np.where(share >= 0.1)[0]
    before = np.arange(ip[0])
    keys = {"A": int(before[np.argmax(r[before].mean(1))]), "B": int(np.argmax(share)), "C": int(min(ip[-1] + 24, len(tt) - 1))}
    assert list(z["point_id"]) == list(g.pids)
    return {"kept": round(float(kept), 3), "clim": 8,
            "hours": [t.strftime("%Y-%m-%dT%H:%M") for t in tt], "label": [t.strftime("%a %H") + "h" for t in tt],
            "x": [round(v, 2) for v in xy[:, 0]], "y": [round(v, 2) for v in xy[:, 1]],
            "mean": r1(r.mean(1)), "front_share": r0(100 * share), "passing": [bool(ip[0] <= i <= ip[-1]) for i in range(len(tt))],
            "keys": {k: {"i": i, "name": n, "map": r1(r[i])} for (k, i), n in zip(keys.items(), ["before", "front passing", "a day after"])},
            "points": {"lon": r3(g.lon), "lat": r3(g.lat)}}


def fixed_sundays(res: Path, g: Grid):
    z = np.load(res / "exp1_forecasts_40x20.npz")
    c = 672
    sun = {s: g.idx(s) for s in set(z["sunday"])}
    o = np.array([sun[s] for s in z["sunday"]])
    col = np.array([g.col[p] for p in z["point_id"]])

    def score(ref, new, value):
        ref, new = ref[:, 4], new[:, 4]
        gap = value - ref
        return 100 * np.nanmean(np.clip((new - ref) / np.where(np.abs(gap) >= 1, gap, np.nan), 0, 1), axis=1)

    def key(day, inp, v):
        return z[f"main|{day}|{inp}|{v}"]

    no, fl = "without time feature", "with Sunday flag"
    groups = []
    for v in [10, 20, 50]:
        ref = key("Sunday", no, None)
        for w in [1, 2, 3]:
            groups.append({"value": v, "setup": f"1 Sunday, {w} week{'s' if w > 1 else ''} ago", "flag": False,
                           "scores": r0(score(ref, z[f"one|{w}|{v}"], v))})
        groups.append({"value": v, "setup": "4 Sundays", "flag": False, "scores": r0(score(ref, key("Sunday", no, v), v))})
        groups.append({"value": v, "setup": "4 Sundays", "flag": True, "scores": r0(score(key("Sunday", fl, None), key("Sunday", fl, v), v))})
        groups.append({"value": v, "setup": "Wednesday (control)", "flag": False, "scores": r0(score(key("Wednesday", no, None), key("Wednesday", no, v), v))})
    for gr in groups:
        s = np.array([np.nan if x is None else x for x in gr["scores"]], float)
        gr.update({"mean": round(float(np.nanmean(s)), 1), "median": round(float(np.nanmedian(s)), 1),
                   "q25": round(float(np.nanpercentile(s, 25)), 1), "q75": round(float(np.nanpercentile(s, 75)), 1)})

    # score vs size of the change (10 and 20 °C together): mean |fixed value - real Sunday temperature| in the history
    sunday_mask = [np.asarray(g.times[i - c : i].day_of_week == 6) for i in o]
    change, vs = [], []
    for v in [10, 20]:
        ch = np.array([np.abs(v - g.T[i - c : i, j][m]).mean() for i, j, m in zip(o, col, sunday_mask)])
        for inp in [no, fl]:
            s = score(key("Sunday", inp, None), key("Sunday", inp, v), v)
            change.append((v, inp, ch, s))
    for inp, flag in [(no, False), (fl, True)]:
        ch = np.concatenate([c_ for v, i, c_, s in change if i == inp])
        s = np.concatenate([s for v, i, c_, s in change if i == inp])
        b = pd.DataFrame({"bin": (ch // 2) * 2 + 1, "s": s}).groupby("bin").s
        st = pd.DataFrame({"q25": b.quantile(0.25), "med": b.median(), "q75": b.quantile(0.75), "n": b.size()})
        st = st[st.n >= 10]
        vs.append({"flag": flag, "change": r1(ch), "score": r0(s), "bins": st.index.tolist(),
                   "median": r1(st.med), "q25": r1(st.q25), "q75": r1(st.q75), "n": st.n.astype(int).tolist()})

    # one case that copies and one that ignores the fixed Sundays (10 °C, no flag): typical of each kind
    s10 = score(key("Sunday", no, None), key("Sunday", no, 10), 10)
    examples = {}
    for kind, sel in [("copies", np.where(s10 >= 75)[0]), ("ignores", np.where(s10 <= 10)[0])]:
        k = int(sel[np.argsort(s10[sel])[len(sel) // 2]])
        i, j = o[k], col[k]
        hist = g.T[i - 8 * 24 : i, j].copy()
        fixed = hist.copy()
        fixed[np.asarray(g.times[i - 8 * 24 : i].day_of_week == 6)] = 10
        q0, q1 = key("Sunday", no, None)[k], key("Sunday", no, 10)[k]
        examples[kind] = {"point": int(z["point_id"][k]), "sunday": str(z["sunday"][k]), "score": round(float(s10[k])),
                          "start": g.times[i].strftime("%Y-%m-%dT%H:%M"), "history": r1(hist), "history_fixed": r1(fixed),
                          "sunday_hours": [int(h) for h in np.where(g.times[i - 8 * 24 : i].day_of_week == 6)[0]],
                          "truth": r1(g.T[i : i + H, j]),
                          "original": {"q10": r1(q0[0]), "q50": r1(q0[4]), "q90": r1(q0[8])},
                          "fixed": {"q10": r1(q1[0]), "q50": r1(q1[4]), "q90": r1(q1[8])}}
    return {"n": len(o), "dates": len(sun), "groups": groups, "score_vs_change": vs, "examples": examples}


def weird_history(res: Path):
    z = np.load(res / "exp6_weird_context.npz")
    z3 = np.load(res / "exp3_forecasts_30perfront.npz")
    ok = (z3["truth"][:, 6] - z3["truth"][:, 6:13].min(1)) >= 2
    assert list(z3["point_id"][ok]) == list(z["point_id"])
    width = lambda f: float((f[:, 8] - f[:, 0]).mean())
    w0 = (z3["A"][ok][:, 8] - z3["A"][ok][:, 0]).mean(axis=1)
    r2 = lambda a: [round(float(v), 2) for v in a]
    sizes = [3, 6, 9, 12, 15]

    def line(n):
        # change per forecast: band with the drops minus the same case without them (size 0 = no drop inserted)
        dw = np.stack([(z[f"drops_{n}_{s}"][:, 8] - z[f"drops_{n}_{s}"][:, 0]).mean(axis=1) - w0 for s in sizes])
        return {"n_drops": n, "sizes": [0, *sizes], "width": [round(width(z3["A"][ok]), 2)] + [round(width(z[f"drops_{n}_{s}"]), 2) for s in sizes],
                "change_mean": [0.0, *r2(dw.mean(1))], "change_q25": [0.0, *r2(np.percentile(dw, 25, axis=1))],
                "change_q75": [0.0, *r2(np.percentile(dw, 75, axis=1))],
                "widen_share": [0.0, *r2((dw > 0.2).mean(1))], "narrow_share": [0.0, *r2((dw < -0.2).mean(1))]}

    # 1 and 2 drops are left out: their drops sit far apart (9 weeks and 3 days back), so they mix count and position
    lines = [line(n) for n in [4, 8, 12, 16]]
    zs = np.load(res / "exp6_slider_fine.npz")
    f = zs["forecast"]
    slider = {"point": int(zs["point_id"]), "start": str(zs["start"])[:16], "n_drops": int(zs["n_drops"]), "sizes": zs["sizes"].tolist(),
              "history": [r1(h) for h in zs["history"]], "truth": r1(zs["truth"]),
              "q10": [r1(x) for x in f[:, 0]], "q50": [r1(x) for x in f[:, 4]], "q90": [r1(x) for x in f[:, 8]]}
    return {"n": len(z["point_id"]), "fronts": len(set(z3["front"][ok])), "lines": lines, "slider": slider}


def drop_position(res: Path):
    """One drop of 8 °C moved through the history: band width per position (all cases) and the example case, every hour."""
    z = np.load(res / "exp6_position.npz")
    c = len(z["history_example"])
    fa, fe = z["forecast_all"].astype(np.float32), z["forecast_example"].astype(np.float32)
    w_all = (fa[:, :, 8] - fa[:, :, 0]).mean(axis=2)
    z6 = np.load(res / "exp6_weird_context.npz")
    z3 = np.load(res / "exp3_forecasts_30perfront.npz")
    ok = (z3["truth"][:, 6] - z3["truth"][:, 6:13].min(1)) >= 2
    assert list(z3["point_id"][ok]) == list(z6["point_id"]) == list(z["point_id"])
    w0_case = (z3["A"][ok][:, 8] - z3["A"][ok][:, 0]).mean(axis=1)
    w0 = float(w0_case.mean())
    dw = w_all - w0_case  # change per case: band with the drop minus the same case without it
    k = list(z6["point_id"]).index(int(z["example_point"]))
    r2 = lambda a: [round(float(v), 2) for v in a]
    return {"n": int(fa.shape[1]), "fronts": len(set(z3["front"][ok])), "size": float(z["size"]), "unchanged": round(w0, 2),
            "all": {"days_back": r1((c - z["starts_all"]) / 24), "mean": r2(w_all.mean(1)),
                    "q25": r1(np.percentile(w_all, 25, axis=1)), "q75": r1(np.percentile(w_all, 75, axis=1)),
                    "change_mean": r2(dw.mean(1)), "change_q25": r2(np.percentile(dw, 25, axis=1)),
                    "change_q75": r2(np.percentile(dw, 75, axis=1)), "widen_share": r2((dw > 0.2).mean(1))},
            "example": {"point": int(z["example_point"]), "history": r1(z["history_example"]), "shape": [round(float(v), 3) for v in z["shape"]],
                        "starts": z["starts_example"].tolist(), "truth": r1(z6["truth"][k]),
                        "q10": [r1(x) for x in fe[:, 0]], "q50": [r1(x) for x in fe[:, 4]], "q90": [r1(x) for x in fe[:, 8]]}}


def where_it_looks(res: Path):
    z = np.load(res / "exp10_occlusion_40x2.npz")
    eff = z["effect"].astype(np.float32).mean(axis=2)  # (cases, hidden hour 1..672): mean over the 24 forecast hours
    out = {"days": 28, "groups": []}
    for name in ["normal day", "cold front"]:
        e = eff[z["group"] == name]
        fold = e.mean(0).reshape(28, 24)  # (days back, hour within the day: 1 = closest)
        tot = fold.sum(1)
        out["groups"].append({"group": name, "n": len(e), "grid": [[round(float(v), 3) for v in row] for row in fold],
                              "per_day": [round(float(v), 2) for v in tot],
                              "last_day_share": round(float(tot[0] / tot.sum()), 3), "last_week_share": round(float(tot[:7].sum() / tot.sum()), 3)})
    lag = np.arange(1, 673)
    m = eff.mean(0)
    ratio = [round(float(m[(lag % 32) == k].mean() / m.mean()), 2) for k in range(32)]
    out["pattern_32h"] = {"ratio_by_lag_mod_32": ratio,
                          "cells": [[int((lg - 1) // 24), int((lg - 1) % 24)] for lg in lag if lg % 32 in (1, 2) and lg > 24]}
    return out


def cold_lasts(res: Path, g: Grid):
    z = np.load(res / "exp5_after_front.npz")
    j = np.array([g.idx(s) for s in z["drop_start"]])
    c = np.array([g.col[p] for p in z["point_id"]])
    span = np.arange(-12, 48 + H)
    a = g.T - g.usual
    tru = np.stack([a[i + span, k] for i, k in zip(j, c)])
    starts = []
    for off in [6, 12, 24, 48]:
        hrs = off + np.arange(H)
        us = np.stack([g.usual[i + hrs, k] for i, k in zip(j, c)])
        starts.append({"start": off, "hours": hrs.tolist(), "forecast": r1((z[f"fc +{off} h"][:, 4] - us).mean(0)),
                       "start_value": round(float(tru[:, np.searchsorted(span, off)].mean()), 2)})
    return {"n": len(j), "truth": {"hours": span.tolist(), "mean": r1(tru.mean(0))}, "starts": starts}


def z_list(a):
    return [int(x) for x in a]


def r3(a):
    return [round(float(x), 3) for x in a]


# ---------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=str(REPO / "data" / "notebooks" / "results"), help="saved forecasts of the notebooks")
    ap.add_argument("--data", default=str(REPO / "data" / "austria_15km"), help="the Austria 15 km dataset")
    ap.add_argument("--out", default=str(HERE / "site" / "data" / "carlos"), help="output folder")
    args = ap.parse_args()
    res, data, out = Path(args.results), Path(args.data), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    g = Grid(data)
    files = {
        "front_explorer": lambda: front_explorer(res, g),
        "catching_up": lambda: catching_up(res),
        "band_honesty": lambda: band_honesty(res),
        "time_curve": lambda: time_curve(res, data, g),
        "fixed_sundays": lambda: fixed_sundays(res, g),
        "weird_history": lambda: weird_history(res),
        "drop_position": lambda: drop_position(res),
        "where_it_looks": lambda: where_it_looks(res),
        "cold_lasts": lambda: cold_lasts(res, g),
    }
    for name, make in files.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(make(), separators=(",", ":")), encoding="utf-8")
        print(f"{path.name:22s} {path.stat().st_size / 1e3:7.0f} kB")


if __name__ == "__main__":
    main()
