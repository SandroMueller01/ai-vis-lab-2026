"""
Build a 1-year hourly weather dataset for ALL OF AUSTRIA on a 5 km grid from GeoSphere Austria
open data (CC BY 4.0). Same method as the Tyrol 1 km dataset, scaled to the country.

  Grid features : INCA analysis (inca-v1-1h-1km), sampled at 3,363 points on a 5 km
                  lattice inside Austria (austria_points_5km.csv), via the API's
                  timeseries endpoint (nearest 1 km INCA cell per point)
  Labels        : foehnix-style mixture model per valley station, using the potential-
                  temperature difference to a crest station of the same region
                  (klima-v2-10min, resampled to hourly)
  Grid labels   : each point takes the label of its nearest valley station (<= 20 km),
                  points farther away stay unlabelled (NaN)

Regions (valley stations -> crest station, foehn type):
  Tyrol Inn/Wipp valley   -> Patscherkofel       south foehn
  Vorarlberg Rhine/Ill    -> Pitztaler Gletscher south foehn (distant crest, see README)
  Salzburg Salzach/Gastein-> Sonnblick           south foehn
  East Tyrol/Carinthia    -> Sonnblick           north foehn

Usage:
  python build_dataset_austria.py --probe     # quick API test (multi-point request)
  python build_dataset_austria.py             # full run, ~255 requests, ~1-1.5 h
Downloads are cached in <out>/raw, so a stopped run can simply be restarted.
Data: GeoSphere Austria, https://data.hub.geosphere.at (CC BY 4.0).
"""

from __future__ import annotations

import argparse
import io
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# Also support running this file directly from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geosphere_http import GeoSphereClient

HERE = Path(__file__).resolve().parent
REPO_DATA = HERE.parents[1] / "data"
API = "https://dataset.api.hub.geosphere.at/v1"
INCA = "inca-v1-1h-1km"
STATION_DS = "klima-v2-10min"
POINTS_FILE = HERE / "austria_points_5km.csv"
GRID_STEP = 5000  # m, Austria Lambert (EPSG:31287)

GRID_PARAMS = ["T2M", "RH2M", "TD2M", "UU", "VV", "P0", "GL", "RR"]
CSV_LIMIT = 1_000_000  # values per CSV request (API limit)
STATION_PARAMS = ["tl", "rf", "dd", "ff", "ffx", "p"]

# id: (name, lat, lon, altitude) - from the klima-v2 station list
STATIONS = {
    39: ("Innsbruck Universitaet", 47.25986, 11.38425, 578.0),
    175: ("Innsbruck Flughafen", 47.25999, 11.35667, 578.0),
    139: ("Steinach am Brenner", 47.09833, 11.46611, 1036.0),
    42: ("Jenbach", 47.38878, 11.75814, 529.0),
    196: ("Patscherkofel", 47.20889, 11.46222, 2251.0),
    24: ("Feldkirch", 47.27111, 9.60972, 438.4),
    171: ("Dornbirn", 47.4325, 9.72556, 407.3),
    181: ("Bludenz", 47.14778, 9.82944, 571.0),
    184: ("Pitztaler Gletscher", 46.92706, 10.87914, 2863.9),
    131: ("Salzburg Flughafen", 47.78944, 13.00861, 430.0),
    14: ("Bischofshofen", 47.40667, 13.22111, 549.9),
    156: ("St.Johann im Pongau", 47.31981, 13.18672, 634.2),
    7: ("Bad Gastein", 47.11056, 13.13336, 1092.0),
    78: ("Rauris", 47.22353, 12.99262, 933.8),
    213: ("Sonnblick", 47.05417, 12.9575, 3109.0),
    55: ("Lienz", 46.82555, 12.80639, 661.0),
    69: ("Obervellach", 46.93528, 13.19444, 688.0),
    137: ("Doellach", 46.95806, 12.9025, 1071.0),
    150: ("Spittal an der Drau", 46.7905, 13.48725, 541.7),
}

# Wind sectors (deg, direction the wind comes FROM) in which foehn is possible.
# These are sensible defaults from valley orientation, NOT tuned per station.
SOUTH, NORTH = (110, 270), (280, 70)
REGIONS = [
    {"name": "Tyrol", "type": "south", "crest": 196, "crest_sector": SOUTH,
     "valley": {39: (90, 290), 175: (90, 290), 139: (120, 250), 42: (60, 290)}},
    {"name": "Vorarlberg", "type": "south", "crest": 184, "crest_sector": SOUTH,
     "valley": {24: (120, 250), 171: (120, 250), 181: (60, 250)}},
    {"name": "Salzburg", "type": "south", "crest": 213, "crest_sector": SOUTH,
     "valley": {131: (100, 230), 14: (120, 240), 156: (100, 250), 7: (120, 240), 78: (120, 240)}},
    {"name": "Carinthia/East Tyrol", "type": "north", "crest": 213, "crest_sector": NORTH,
     "valley": {55: (280, 80), 69: (280, 80), 137: (280, 80), 150: (270, 60)}},
]

get = GeoSphereClient(retries=10).get


def iso(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M")


# ----------------------------------------------------------------------- stations
def download_stations(start, end, raw: Path) -> pd.DataFrame:
    ids = sorted({r["crest"] for r in REGIONS} | {v for r in REGIONS for v in r["valley"]})
    groups = [ids[i : i + 10] for i in range(0, len(ids), 10)]  # keep each request < 1M values
    edges = sorted({start, *[e for e in pd.date_range(start, end, freq="QS-JAN")], end})
    frames = []
    for gi, grp in enumerate(groups):
        for a, b in pairwise(edges):
            f = raw / f"stations_g{gi}_{a:%Y%m%d}_{b:%Y%m%d}.csv"
            if not f.exists():
                print(f"  stations group {gi + 1}/{len(groups)}  {a:%Y-%m-%d} -> {b:%Y-%m-%d}")
                r = get(f"{API}/station/historical/{STATION_DS}", {
                    "parameters": ",".join(STATION_PARAMS), "station_ids": ",".join(map(str, grp)),
                    "start": iso(a), "end": iso(b - pd.Timedelta("10min")), "output_format": "csv"})
                f.write_text(r.text, encoding="utf-8")
            frames.append(pd.read_csv(f))
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.drop_duplicates(["time", "station"]).sort_values(["station", "time"])


def to_hourly(df10: pd.DataFrame) -> pd.DataFrame:
    """10-min -> hourly, labelled at the END of the hour (matches INCA analysis time)."""
    out = []
    for sid, g in df10.groupby("station"):
        g = g.set_index("time")
        rad = np.deg2rad(g["dd"])
        g = g.assign(_u=-g["ff"] * np.sin(rad), _v=-g["ff"] * np.cos(rad))
        rs = g.resample("1h", label="right", closed="right")
        h = pd.DataFrame({"tl": rs["tl"].mean(), "rf": rs["rf"].mean(), "ff": rs["ff"].mean(),
                          "ffx": rs["ffx"].max(), "p": rs["p"].mean(), "_u": rs["_u"].mean(),
                          "_v": rs["_v"].mean(), "n": rs["tl"].count()})
        h["dd"] = (np.rad2deg(np.arctan2(-h["_u"], -h["_v"])) + 360) % 360
        h = h.drop(columns=["_u", "_v"])
        h.loc[h["n"] < 4, :] = np.nan
        h["station"] = sid
        out.append(h.drop(columns="n").reset_index())
    return pd.concat(out, ignore_index=True)


# ------------------------------------------------------------- foehnix-style model
def potential_temperature(t_c, p_hpa):
    return (t_c + 273.15) * (1000.0 / p_hpa) ** 0.2854


def in_sector(dd, sector):
    lo, hi = sector
    return (dd >= lo) & (dd <= hi) if lo <= hi else (dd >= lo) | (dd <= hi)


def fit_foehnix(y, X, iters=200, tol=1e-6):
    """2-component Gaussian mixture on y with logistic concomitant (foehnix idea).
    Foehn = component with the LOWER mean of dtheta."""
    n = len(y)
    Xs = (X - X.mean(0)) / X.std(0)
    Z = np.column_stack([np.ones(n), Xs])
    post = (y < np.median(y)).astype(float)
    beta = np.zeros(Z.shape[1])
    ll_old = -np.inf
    for _ in range(iters):
        w1, w0 = post, 1 - post
        mu1, mu0 = np.average(y, weights=w1), np.average(y, weights=w0)
        s1 = np.sqrt(np.average((y - mu1) ** 2, weights=w1)) + 1e-6
        s0 = np.sqrt(np.average((y - mu0) ** 2, weights=w0)) + 1e-6
        for _ in range(5):
            pi = 1 / (1 + np.exp(-Z @ beta))
            W = pi * (1 - pi) + 1e-9
            H = Z.T @ (Z * W[:, None]) + 1e-6 * np.eye(Z.shape[1])
            beta = beta + np.linalg.solve(H, Z.T @ (post - pi))
        pi = np.clip(1 / (1 + np.exp(-Z @ beta)), 1e-9, 1 - 1e-9)
        d1 = pi * np.exp(-0.5 * ((y - mu1) / s1) ** 2) / s1
        d0 = (1 - pi) * np.exp(-0.5 * ((y - mu0) / s0) ** 2) / s0
        tot = d1 + d0 + 1e-300
        post = d1 / tot
        ll = np.log(tot).sum()
        if abs(ll - ll_old) < tol * abs(ll):
            break
        ll_old = ll
    if mu1 > mu0:
        post, (mu1, mu0) = 1 - post, (mu0, mu1)
    return post, mu1, mu0


def label_stations(hourly: pd.DataFrame) -> pd.DataFrame:
    wide = hourly.pivot(index="time", columns="station")
    have = set(wide.columns.get_level_values("station"))
    out = []
    for reg in REGIONS:
        if reg["crest"] not in have:
            print(f"  ! crest {STATIONS[reg['crest']][0]} missing, region {reg['name']} skipped")
            continue
        crest = wide.xs(reg["crest"], axis=1, level="station")
        th_c = potential_temperature(crest["tl"], crest["p"])
        for sid, vsector in reg["valley"].items():
            if sid not in have:
                print(f"  ! no data for {STATIONS[sid][0]}, skipped")
                continue
            val = wide.xs(sid, axis=1, level="station")
            df = pd.DataFrame({
                "time": wide.index, "station": sid, "station_name": STATIONS[sid][0],
                "region": reg["name"], "foehn_type": reg["type"], "crest_station": reg["crest"],
                "dtheta": (th_c - potential_temperature(val["tl"], val["p"])).values,
                "rf": val["rf"].values, "ff": val["ff"].values, "ffx": val["ffx"].values,
                "dd": val["dd"].values, "crest_dd": crest["dd"].values, "crest_ff": crest["ff"].values})
            ok = df[["dtheta", "rf", "ff", "dd", "crest_dd"]].notna().all(axis=1)
            sector = ok & in_sector(df["dd"], vsector) & in_sector(df["crest_dd"], reg["crest_sector"])
            prob = pd.Series(np.nan, index=df.index)
            prob[ok & ~sector] = 0.0
            m = sector.values
            if m.sum() < 200:
                print(f"  ! {STATIONS[sid][0]}: only {m.sum()} hours in wind sector, skipped")
                continue
            p, mu_f, mu_n = fit_foehnix(df.loc[m, "dtheta"].to_numpy(), df.loc[m, ["rf", "ff"]].to_numpy())
            prob[m] = p
            df["foehn_prob"] = prob
            df["foehn"] = (prob >= 0.5).astype("float").where(prob.notna())
            print(f"  {reg['name'][:10]:10s} {STATIONS[sid][0]:24s} foehn {df['foehn'].mean() * 100:5.1f}% "
                  f"of valid hours   dtheta foehn {mu_f:5.1f}K vs no-foehn {mu_n:5.1f}K")
            out.append(df)
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------- grid
def download_points(points: pd.DataFrame, start, end, raw: Path) -> list:
    hours = int((end - start) / pd.Timedelta("1h"))
    per_req = max(1, CSV_LIMIT // (len(GRID_PARAMS) * hours))
    batches = [points.iloc[i : i + per_req] for i in range(0, len(points), per_req)]
    done = [(raw / f"inca_pts_{b.point_id.iloc[0]:04d}_{b.point_id.iloc[-1]:04d}.csv", b) for b in batches]
    pending = sum(not f.exists() for f, _ in done)
    print(f"  {len(points)} points, {per_req} per request -> {len(batches)} requests "
          f"({pending} uncached)")
    if pending:
        print(f"  rough download estimate: ~{max(1, pending / 240 * 60):.0f}+ min at 240 requests/hour "
              "(remaining quota, reset timing and transfer speed affect actual time)")
    else:
        print("  all INCA batches cached; no downloads needed")
    for bi, (f, b) in enumerate(done):
        if not f.exists():
            print(f"  INCA batch {bi + 1}/{len(batches)}")
            r = get(f"{API}/timeseries/historical/{INCA}", {
                "parameters": ",".join(GRID_PARAMS),
                "lat_lon": [f"{la},{lo}" for la, lo in zip(b.lat, b.lon)],
                "start": iso(start), "end": iso(end - pd.Timedelta("1h")), "output_format": "csv"})
            d = pd.read_csv(io.StringIO(r.text))
            if d.groupby(["lat", "lon"]).ngroups != len(b):
                raise RuntimeError(f"asked for {len(b)} points but got {d.groupby(['lat', 'lon']).ngroups}")
            f.write_text(r.text, encoding="utf-8")
    return done


def assign_points(d: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Map the INCA cell coordinates returned by the API back to our point_ids (nearest)."""
    d = d.rename(columns={c: c.split(" [")[0] for c in d.columns})
    cells = d[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
    dist = (cells.lat.values[:, None] - b.lat.values[None, :]) ** 2 + \
           ((cells.lon.values[:, None] - b.lon.values[None, :]) * 0.68) ** 2
    cells["point_id"] = b.point_id.values[dist.argmin(1)]
    if cells.point_id.duplicated().any():
        raise RuntimeError("two INCA cells mapped to the same point")
    d = d.merge(cells, on=["lat", "lon"]).rename(columns={"lat": "inca_lat", "lon": "inca_lon"})
    d["time"] = pd.to_datetime(d["time"], utc=True)
    return d


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.deg2rad(lat1), np.deg2rad(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.deg2rad(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def build_outputs(batches, points, labels, start, end, max_dist_km, out: Path):
    """Write grid_long.parquet batch by batch (low RAM) and fill the (time, y, x) cube."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    ids = list(labels["station"].unique())
    dist = np.stack([haversine_km(points.lat.values, points.lon.values, STATIONS[s][1], STATIONS[s][2]) for s in ids])
    points = points.assign(label_station=np.array(ids)[dist.argmin(0)], label_dist_km=dist.min(0).astype("float32"))
    reg = labels.drop_duplicates("station").set_index("station")["region"]
    points["label_region"] = points.label_station.map(reg)
    far = points.label_dist_km > max_dist_km
    points.loc[far, "label_station"] = -1
    points.loc[far, "label_region"] = None
    lab = labels[["time", "station", "foehn_prob", "foehn"]].rename(columns={"station": "label_station"})

    times = pd.date_range(start, end, freq="1h", inclusive="left")
    xs = np.arange(points.x.min(), points.x.max() + GRID_STEP, GRID_STEP)
    ys = np.arange(points.y.min(), points.y.max() + GRID_STEP, GRID_STEP)
    cube_vars = [*GRID_PARAMS, "wind_speed", "wind_dir", "foehn_prob", "foehn"]
    cube = {v: np.full((len(times), len(ys), len(xs)), np.nan, dtype="float32") for v in cube_vars}
    cols = ["point_id", "time", "x", "y", "lat", "lon", *GRID_PARAMS, "wind_speed", "wind_dir",
            "foehn_prob", "foehn", "label_station", "label_region", "label_dist_km", "inca_lat", "inca_lon"]

    writer, n_rows = None, 0
    for f, b in batches:
        d = assign_points(pd.read_csv(f), b)
        d = d.merge(points, on="point_id", how="left").merge(lab, on=["time", "label_station"], how="left")
        d["wind_speed"] = np.hypot(d.UU, d.VV)
        d["wind_dir"] = (np.rad2deg(np.arctan2(-d.UU, -d.VV)) + 360) % 360
        d = d[cols].sort_values(["point_id", "time"])
        for c in d.select_dtypes("float64").columns:
            d[c] = d[c].astype("float32")
        ti = times.get_indexer(d.time)
        ok = ti >= 0
        yi, xi = np.searchsorted(ys, d.y.values), np.searchsorted(xs, d.x.values)
        for v in cube_vars:
            cube[v][ti[ok], yi[ok], xi[ok]] = d[v].values[ok]
        table = pa.Table.from_pandas(d, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(out / "grid_long.parquet", table.schema, compression="zstd")
        writer.write_table(table)
        n_rows += len(d)
    writer.close()

    data = {v: (("time", "y", "x"), a) for v, a in cube.items()}
    pxi, pyi = np.searchsorted(xs, points.x.values), np.searchsorted(ys, points.y.values)
    for v in ["lat", "lon", "label_dist_km"]:
        a = np.full((len(ys), len(xs)), np.nan, dtype="float32"); a[pyi, pxi] = points[v].values
        data[v] = (("y", "x"), a)
    a = np.full((len(ys), len(xs)), -1, dtype="int32"); a[pyi, pxi] = points.label_station.values
    data["label_station"] = (("y", "x"), a)
    ds = xr.Dataset(data, coords={"time": times.tz_localize(None), "y": ys, "x": xs})
    ds.attrs.update(crs="EPSG:31287 (Austria Lambert), 5 km lattice of INCA 1 km cells; NaN outside Austria",
                    source="GeoSphere Austria Data Hub (INCA inca-v1-1h-1km, klima-v2-10min), CC BY 4.0",
                    labels="foehnix-style mixture on theta(crest)-theta(valley); points take nearest valley station")
    ds.to_netcdf(out / "grid.nc", encoding={v: {"zlib": True, "complevel": 4} for v in ds.data_vars})
    points.to_csv(out / "points_with_labels.csv", index=False)
    return n_rows, points, len(times)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2025-10-01")
    ap.add_argument("--end", default="2026-10-01", help="exclusive")
    ap.add_argument("--out", default=str(REPO_DATA / "austria_5km"))
    ap.add_argument("--max-dist-km", type=float, default=20)
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    out = Path(args.out); raw = out / "raw"; raw.mkdir(parents=True, exist_ok=True)
    start, end = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC")
    points = pd.read_csv(POINTS_FILE)

    if args.probe:
        b = points.sample(5, random_state=0)
        r = get(f"{API}/timeseries/historical/{INCA}", {
            "parameters": ",".join(GRID_PARAMS), "lat_lon": [f"{la},{lo}" for la, lo in zip(b.lat, b.lon)],
            "start": iso(start), "end": iso(start + pd.Timedelta("1h")), "output_format": "csv"})
        d = pd.read_csv(io.StringIO(r.text))
        print(r.text[:800])
        n = d.groupby(["lat", "lon"]).ngroups
        print(f"\nrequested 5 points, got {n} ->", "OK" if n == 5 else "PROBLEM: point count mismatch")
        print(assign_points(d, b)[["point_id", "inca_lat", "inca_lon"]].drop_duplicates().merge(b, on="point_id"))
        ids = ",".join(map(str, sorted({r["crest"] for r in REGIONS} | {v for r in REGIONS for v in r["valley"]})))
        r = get(f"{API}/station/historical/{STATION_DS}", {"parameters": ",".join(STATION_PARAMS),
                "station_ids": ids, "start": iso(start), "end": iso(start), "output_format": "csv"})
        s = pd.read_csv(io.StringIO(r.text))
        print(f"\nstations answering: {s.station.nunique()} of {len(ids.split(','))}")
        print(s.to_string(index=False))
        return

    print("1/4 station data")
    hourly = to_hourly(download_stations(start, end, raw))
    hourly.to_parquet(out / "stations_hourly.parquet", index=False)

    print("2/4 foehn labels at stations")
    labels = label_stations(hourly)
    labels.to_parquet(out / "station_labels.parquet", index=False)

    print("3/4 INCA at 5 km points")
    batches = download_points(points, start, end, raw)

    print("4/4 attach labels + write")
    n_rows, pts, n_hours = build_outputs(batches, points, labels, start, end, args.max_dist_km, out)
    print(f"\ndone: {len(pts)} points x {n_hours} hours = {n_rows:,} rows")
    print(f"points with a label: {(pts.label_station >= 0).sum()} of {len(pts)}")
    print(f"files in {out.resolve()}")


if __name__ == "__main__":
    main()
