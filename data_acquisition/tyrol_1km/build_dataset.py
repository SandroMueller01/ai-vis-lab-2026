"""
Build a 1-year gridded hourly weather dataset (with foehn labels) for the Wipp/Inn valley (Tyrol) from
GeoSphere Austria open data (CC BY 4.0).

  Grid features : INCA analysis, 1 km, hourly        (inca-v1-1h-1km)
  Labels        : foehnix-style mixture model at valley stations, using the
                  potential-temperature difference to the crest station
                  Patscherkofel (klima-v2-10min, resampled to hourly)
  Grid labels   : each grid cell takes the label of its nearest valley station

Outputs (in --out, default <repo>/data/tyrol_1km):
  stations_hourly.parquet   hourly station observations
  station_labels.parquet    hourly foehn probability + 0/1 label per valley station
  grid.nc                   (time, y, x) INCA fields + foehn_prob + foehn
  grid_long.parquet         long format: one row per (cell, hour) -> TiRex-2 input

Usage:
  python build_dataset.py --probe            # 2-hour test request, prints structure
  python build_dataset.py                    # full run (default 2025-10-01 .. 2026-10-01)
  python build_dataset.py --coarsen 2        # 2 km cells instead of 1 km

Downloads are cached in <out>/raw, so a crashed run can simply be restarted.
Data: GeoSphere Austria, https://data.hub.geosphere.at (CC BY 4.0).
"""

from __future__ import annotations

import argparse
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# Also support running this file directly from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geosphere_http import GeoSphereClient

REPO_DATA = Path(__file__).resolve().parents[2] / "data"
API = "https://dataset.api.hub.geosphere.at/v1"
INCA = "inca-v1-1h-1km"
STATION_DS = "klima-v2-10min"

# Innsbruck - Wipp valley - Brenner. south, west, north, east (EPSG:4326)
BBOX = (46.95, 11.00, 47.45, 11.75)
GRID_PARAMS = ["T2M", "RH2M", "TD2M", "UU", "VV", "P0", "GL", "RR"]
GRID_CHUNK_HOURS = 24 * 10  # 8 params * ~3,600 cells * 240 h ~ 7M values < 10M NetCDF limit

STATION_PARAMS = ["tl", "rf", "dd", "ff", "ffx", "p"]  # temp, RH, dir, mean wind, gust, station pressure

# Crest station (upstream air for south foehn) and valley stations to label.
# Wind sectors are the directions (deg, "from") in which foehn is possible at
# that station; outside them the hour is labelled "no foehn" (foehnix convention).
CREST = {"id": 196, "name": "Patscherkofel", "sector": (110, 270)}
VALLEY = [
    {"id": 39, "name": "Innsbruck Universitaet", "sector": (90, 290)},
    {"id": 175, "name": "Innsbruck Flughafen", "sector": (90, 290)},
    {"id": 139, "name": "Steinach am Brenner", "sector": (120, 250)},
]
STATION_META = {  # id: (lat, lon, altitude m) from the klima-v2 station list
    39: (47.25986, 11.38425, 578.0),
    175: (47.25999, 11.35667, 578.0),
    139: (47.09833, 11.46611, 1036.0),
    196: (47.20889, 11.46222, 2251.0),
}

get = GeoSphereClient(retries=8).get


def iso(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M")


# ----------------------------------------------------------------------- stations
def download_stations(start: pd.Timestamp, end: pd.Timestamp, raw: Path) -> pd.DataFrame:
    ids = [CREST["id"]] + [v["id"] for v in VALLEY]
    frames = []
    # 6 params * 4 stations * ~13k 10-min steps per quarter ~ 320k values < 1M CSV limit
    edges = list(pd.date_range(start, end, freq="QS-JAN")) + [end]
    edges = sorted(set([start] + [e for e in edges if start <= e <= end]))
    for a, b in pairwise(edges):
        f = raw / f"stations_{a:%Y%m%d}_{b:%Y%m%d}.csv"
        if not f.exists():
            print(f"  stations {a:%Y-%m-%d} -> {b:%Y-%m-%d}")
            r = get(
                f"{API}/station/historical/{STATION_DS}",
                {
                    "parameters": ",".join(STATION_PARAMS),
                    "station_ids": ",".join(map(str, ids)),
                    "start": iso(a),
                    "end": iso(b - pd.Timedelta("10min")),
                    "output_format": "csv",
                },
            )
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
        h = pd.DataFrame(
            {
                "tl": rs["tl"].mean(),
                "rf": rs["rf"].mean(),
                "ff": rs["ff"].mean(),
                "ffx": rs["ffx"].max(),
                "p": rs["p"].mean(),
                "_u": rs["_u"].mean(),
                "_v": rs["_v"].mean(),
                "n": rs["tl"].count(),
            }
        )
        h["dd"] = (np.rad2deg(np.arctan2(-h["_u"], -h["_v"])) + 360) % 360
        h = h.drop(columns=["_u", "_v"])
        h.loc[h["n"] < 4, :] = np.nan  # need >= 4 of 6 values per hour
        h["station"] = sid
        out.append(h.drop(columns="n").reset_index())
    return pd.concat(out, ignore_index=True)


# ------------------------------------------------------------- foehnix-style model
def potential_temperature(t_c, p_hpa):
    return (t_c + 273.15) * (1000.0 / p_hpa) ** 0.2854


def in_sector(dd, sector):
    lo, hi = sector
    return (dd >= lo) & (dd <= hi) if lo <= hi else (dd >= lo) | (dd <= hi)


def fit_foehnix(y: np.ndarray, X: np.ndarray, iters: int = 200, tol: float = 1e-6):
    """Two-component Gaussian mixture on y with a logistic concomitant model
    (prior foehn probability depends on X), fitted by EM - the foehnix idea
    (Plavcan & Mayr / Stauffer et al., Univ. Innsbruck).

    Returns posterior foehn probability for each row and the fitted parameters.
    The foehn component is the one with the LOWER mean of y = theta_crest - theta_valley
    (foehn mixes the valley air down to the crest's potential temperature).
    """
    n = len(y)
    Xs = (X - X.mean(0)) / X.std(0)
    Z = np.column_stack([np.ones(n), Xs])
    # init: split at median
    post = (y < np.median(y)).astype(float)
    beta = np.zeros(Z.shape[1])
    ll_old = -np.inf
    for _ in range(iters):
        # M-step: Gaussians
        w1, w0 = post, 1 - post
        mu1, mu0 = np.average(y, weights=w1), np.average(y, weights=w0)
        s1 = np.sqrt(np.average((y - mu1) ** 2, weights=w1)) + 1e-6
        s0 = np.sqrt(np.average((y - mu0) ** 2, weights=w0)) + 1e-6
        # M-step: logistic concomitant with soft targets (a few IRLS steps)
        for _ in range(5):
            pi = 1 / (1 + np.exp(-Z @ beta))
            W = pi * (1 - pi) + 1e-9
            H = Z.T @ (Z * W[:, None]) + 1e-6 * np.eye(Z.shape[1])
            beta = beta + np.linalg.solve(H, Z.T @ (post - pi))
        pi = np.clip(1 / (1 + np.exp(-Z @ beta)), 1e-9, 1 - 1e-9)
        # E-step
        d1 = pi * np.exp(-0.5 * ((y - mu1) / s1) ** 2) / s1
        d0 = (1 - pi) * np.exp(-0.5 * ((y - mu0) / s0) ** 2) / s0
        tot = d1 + d0 + 1e-300
        post = d1 / tot
        ll = np.log(tot).sum()
        if abs(ll - ll_old) < tol * abs(ll):
            break
        ll_old = ll
    if mu1 > mu0:  # make component 1 = foehn = lower mean
        post, (mu1, mu0), (s1, s0) = 1 - post, (mu0, mu1), (s0, s1)
    return post, {"mu_foehn": mu1, "sd_foehn": s1, "mu_nofoehn": mu0, "sd_nofoehn": s0}


def label_stations(hourly: pd.DataFrame) -> pd.DataFrame:
    wide = hourly.pivot(index="time", columns="station")
    crest = wide.xs(CREST["id"], axis=1, level="station")
    th_c = potential_temperature(crest["tl"], crest["p"])
    out = []
    for v in VALLEY:
        if v["id"] not in wide.columns.get_level_values("station"):
            print(f"  ! no data for {v['name']}, skipped")
            continue
        val = wide.xs(v["id"], axis=1, level="station")
        df = pd.DataFrame(
            {
                "time": wide.index,
                "station": v["id"],
                "station_name": v["name"],
                "dtheta": (th_c - potential_temperature(val["tl"], val["p"])).values,
                "rf": val["rf"].values,
                "ff": val["ff"].values,
                "ffx": val["ffx"].values,
                "dd": val["dd"].values,
                "crest_dd": crest["dd"].values,
                "crest_ff": crest["ff"].values,
            }
        )
        ok = df[["dtheta", "rf", "ff", "dd", "crest_dd"]].notna().all(axis=1)
        sector = ok & in_sector(df["dd"], v["sector"]) & in_sector(df["crest_dd"], CREST["sector"])
        prob = pd.Series(np.nan, index=df.index)
        prob[ok & ~sector] = 0.0  # wrong wind direction -> no foehn
        m = sector.values
        p, params = fit_foehnix(df.loc[m, "dtheta"].to_numpy(), df.loc[m, ["rf", "ff"]].to_numpy())
        prob[m] = p
        df["foehn_prob"] = prob
        df["foehn"] = (prob >= 0.5).astype("float").where(prob.notna())
        print(
            f"  {v['name']:24s} foehn hours: {int(df['foehn'].sum()):5d} "
            f"({df['foehn'].mean() * 100:4.1f}% of valid)  "
            f"dtheta foehn {params['mu_foehn']:.1f}K vs no-foehn {params['mu_nofoehn']:.1f}K"
        )
        out.append(df)
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------- grid
def download_grid(start, end, raw: Path) -> xr.Dataset:
    edges = list(pd.date_range(start, end, freq=f"{GRID_CHUNK_HOURS}h"))
    if edges[-1] < end:
        edges.append(end)
    files = []
    for a, b in pairwise(edges):
        f = raw / f"inca_{a:%Y%m%d%H}_{b:%Y%m%d%H}.nc"
        if not f.exists():
            print(f"  INCA {a:%Y-%m-%d} -> {b:%Y-%m-%d}")
            r = get(
                f"{API}/grid/historical/{INCA}",
                {
                    "parameters": ",".join(GRID_PARAMS),
                    "start": iso(a),
                    "end": iso(b - pd.Timedelta("1h")),
                    "bbox": ",".join(map(str, BBOX)),
                    "output_format": "netcdf",
                },
            )
            f.write_bytes(r.content)
        files.append(f)
    parts = [xr.load_dataset(f) for f in files]  # load + close (Windows file locks)
    ds = xr.concat(parts, dim="time")
    _, idx = np.unique(ds["time"].values, return_index=True)
    return ds.isel(time=idx)


def grid_latlon(ds: xr.Dataset):
    """2-D lat/lon arrays for the grid, whatever the file calls them."""
    for la, lo in (("lat", "lon"), ("latitude", "longitude")):
        if la in ds.variables and lo in ds.variables:
            lat, lon = ds[la], ds[lo]
            if lat.ndim == 1 and lat.dims != lon.dims:
                lon2, lat2 = np.meshgrid(lon.values, lat.values)
                return lat2, lon2
            return lat.values, lon.values
    from pyproj import Transformer  # x/y in Austria Lambert (EPSG:31287)

    xx, yy = np.meshgrid(ds["x"].values, ds["y"].values)
    tr = Transformer.from_crs(31287, 4326, always_xy=True)
    lon, lat = tr.transform(xx, yy)
    return lat, lon


def spatial_dims(ds: xr.Dataset):
    dims = [d for d in ds[GRID_PARAMS[0]].dims if d != "time"]
    assert len(dims) == 2, f"unexpected dims {ds[GRID_PARAMS[0]].dims}"
    return dims  # (y-like, x-like)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.deg2rad(lat1), np.deg2rad(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.deg2rad(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def attach_labels(ds: xr.Dataset, labels: pd.DataFrame, max_dist_km: float) -> xr.Dataset:
    ydim, xdim = spatial_dims(ds)
    lat, lon = grid_latlon(ds)
    ids = [s for s in labels["station"].unique()]
    dist = np.stack([haversine_km(lat, lon, *STATION_META[s][:2]) for s in ids])
    nearest = np.argmin(dist, axis=0)
    ds = ds.assign_coords(lat=((ydim, xdim), lat), lon=((ydim, xdim), lon))
    ds["label_station"] = ((ydim, xdim), np.array(ids)[nearest])
    ds["label_dist_km"] = ((ydim, xdim), dist.min(axis=0).astype("float32"))

    times = pd.DatetimeIndex(ds["time"].values)
    times = times.tz_localize("UTC") if times.tz is None else times.tz_convert("UTC")
    prob = np.full((len(times), len(ids)), np.nan, dtype="float32")
    for k, s in enumerate(ids):
        ser = labels[labels["station"] == s].set_index("time")["foehn_prob"]
        prob[:, k] = ser.reindex(times).to_numpy()
    grid_prob = prob[:, nearest]  # (time, y, x)
    grid_prob[:, dist.min(axis=0) > max_dist_km] = np.nan  # too far from any valley station
    ds["foehn_prob"] = (("time", ydim, xdim), grid_prob)
    ds["foehn"] = (("time", ydim, xdim), np.where(np.isnan(grid_prob), np.nan, grid_prob >= 0.5).astype("float32"))

    ds["wind_speed"] = np.hypot(ds["UU"], ds["VV"]).astype("float32")
    ds["wind_dir"] = ((np.rad2deg(np.arctan2(-ds["UU"], -ds["VV"])) + 360) % 360).astype("float32")
    ds.attrs.update(
        source="GeoSphere Austria Data Hub (INCA inca-v1-1h-1km, klima-v2-10min), CC BY 4.0",
        labels="foehnix-style mixture on theta(Patscherkofel)-theta(valley); grid cells take nearest valley station",
    )
    return ds


def write_long(ds: xr.Dataset, path: Path) -> int:
    """Long format (one row per cell and hour), written row-by-row of the grid to keep RAM low."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    ydim, xdim = spatial_dims(ds)
    ny, nx = ds.sizes[ydim], ds.sizes[xdim]
    keep = GRID_PARAMS + ["wind_speed", "wind_dir", "foehn_prob", "foehn"]
    times = ds["time"].values
    writer, n = None, 0
    for j in range(ny):
        row = ds.isel({ydim: j})
        nt = len(times)
        cols = {
            "cell_id": np.repeat(np.arange(j * nx, (j + 1) * nx), nt).astype("int32"),
            "time": np.tile(times, nx),
            "lat": np.repeat(row["lat"].values, nt).astype("float32"),
            "lon": np.repeat(row["lon"].values, nt).astype("float32"),
            "label_station": np.repeat(row["label_station"].values, nt).astype("int32"),
            "label_dist_km": np.repeat(row["label_dist_km"].values, nt).astype("float32"),
        }
        for v in keep:
            cols[v] = row[v].transpose(xdim, "time").values.ravel().astype("float32")
        table = pa.table(cols)
        if writer is None:
            writer = pq.ParquetWriter(path, table.schema, compression="zstd")
        writer.write_table(table)
        n += table.num_rows
    writer.close()
    return n


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2025-10-01")
    ap.add_argument("--end", default="2026-10-01", help="exclusive")
    ap.add_argument("--out", default=str(REPO_DATA / "tyrol_1km"))
    ap.add_argument("--coarsen", type=int, default=1, help="average NxN cells (2 -> 2 km)")
    ap.add_argument("--max-dist-km", type=float, default=20, help="no label for cells farther from a valley station")
    ap.add_argument("--probe", action="store_true", help="tiny request, print structure, exit")
    args = ap.parse_args()

    out = Path(args.out)
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")

    if args.probe:
        r = get(
            f"{API}/grid/historical/{INCA}",
            {"parameters": ",".join(GRID_PARAMS), "start": iso(start), "end": iso(start + pd.Timedelta("1h")),
             "bbox": ",".join(map(str, BBOX)), "output_format": "netcdf"},
        )
        probe_file = raw / "probe.nc"
        probe_file.write_bytes(r.content)
        ds = xr.load_dataset(probe_file)
        print(ds)
        print("cells:", np.prod([ds.sizes[d] for d in spatial_dims(ds)]))
        r = get(f"{API}/station/historical/{STATION_DS}",
                {"parameters": ",".join(STATION_PARAMS), "station_ids": "39,196",
                 "start": iso(start), "end": iso(start + pd.Timedelta("30min")), "output_format": "csv"})
        print(r.text)
        return

    print("1/4 station data")
    hourly = to_hourly(download_stations(start, end, raw))
    hourly.to_parquet(out / "stations_hourly.parquet", index=False)

    print("2/4 foehn labels at stations")
    labels = label_stations(hourly)
    labels.to_parquet(out / "station_labels.parquet", index=False)

    print("3/4 INCA grid")
    ds = download_grid(start, end, raw)
    if args.coarsen > 1:
        ydim, xdim = spatial_dims(ds)
        ds = ds.coarsen({ydim: args.coarsen, xdim: args.coarsen}, boundary="trim").mean()

    print("4/4 attach labels + write")
    ds = attach_labels(ds, labels, args.max_dist_km)
    enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
    ds.to_netcdf(out / "grid.nc", encoding=enc)
    n_rows = write_long(ds, out / "grid_long.parquet")
    ydim, xdim = spatial_dims(ds)
    n_cells = ds.sizes[ydim] * ds.sizes[xdim]
    print(f"\ndone: {n_cells} cells x {ds.sizes['time']} hours = {n_rows:,} rows")
    print(f"foehn share (grid, valid hours): {np.nanmean(ds['foehn'].values) * 100:.1f}%")
    print(f"files in {out.resolve()}")


if __name__ == "__main__":
    main()
