"""
Phase I dataset: the Austria 5 km build thinned out to a coarser lattice (default 15 km,
378 points). No new download, just every 3rd point in x and y of the 5 km lattice, so
both pairs work with exactly the same locations.

  Selection : points whose Austria Lambert coordinates (EPSG:31287) are multiples of
              --spacing-km, which keeps a regular lattice
  Values    : copied unchanged from data/austria_5km (INCA features, foehn context)

Outputs, written to --out (default data/austria_15km/):
  grid_long.parquet         one row per (point, hour), same columns as the 5 km build
  points_with_labels.csv    the selected points
  stations_hourly.parquet,  station observations and foehn labels, copied for context
  station_labels.parquet

Event labels for these points: run events/build_events.py --data data/austria_15km.

Usage:
  python data_acquisition/austria_15km/build_subset.py
  python data_acquisition/austria_15km/build_subset.py --spacing-km 10
Data: GeoSphere Austria, https://data.hub.geosphere.at (CC BY 4.0).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

REPO_DATA = Path(__file__).resolve().parents[2] / "data"
STATION_FILES = ["stations_hourly.parquet", "station_labels.parquet"]


def select(points: pd.DataFrame, spacing_km: float) -> pd.DataFrame:
    """Points of the 5 km lattice that lie on a coarser lattice with the given spacing."""
    step = round(spacing_km * 1000)
    keep = (points.x % step == 0) & (points.y % step == 0)
    return points[keep].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(REPO_DATA / "austria_5km"), help="Austria 5 km build")
    ap.add_argument("--out", default=str(REPO_DATA / "austria_15km"))
    ap.add_argument("--spacing-km", type=float, default=15, help="multiple of 5 km")
    args = ap.parse_args()
    if args.spacing_km % 5:
        ap.error("--spacing-km must be a multiple of 5")

    import pyarrow.parquet as pq

    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"1/3 select points ({args.spacing_km:g} km)")
    points = select(pd.read_csv(src / "points_with_labels.csv"), args.spacing_km)
    points.to_csv(out / "points_with_labels.csv", index=False)
    print(f"  {len(points)} points")

    print("2/3 filter grid_long.parquet")
    table = pq.read_table(src / "grid_long.parquet", filters=[("point_id", "in", points.point_id.tolist())])
    pq.write_table(table, out / "grid_long.parquet", compression="zstd")
    print(f"  {table.num_rows:,d} rows")

    print("3/3 copy station files")
    for name in STATION_FILES:
        shutil.copy2(src / name, out / name)
    print(f"done: {out}  (next: python data_acquisition/events/build_events.py --data {out})")


if __name__ == "__main__":
    main()
