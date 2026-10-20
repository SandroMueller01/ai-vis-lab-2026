# Data acquisition — Austrian foehn datasets

Two builders that download hourly weather fields from the
[GeoSphere Austria Data Hub](https://data.hub.geosphere.at) (CC BY 4.0) and
attach a **foehn / no-foehn label** to every grid cell and hour. The outputs are
multivariate hourly time series, one per location, which is the input shape for
TiRex-2.

Both default to the period **2025-10-01 → 2026-10-01** (one year, 8,760 hours).

| | `tyrol_1km/` | `austria_5km/` |
|---|---|---|
| Area | Innsbruck – Wipp valley – Brenner (bbox 46.95–47.45 N, 11.00–11.75 E) | All of Austria |
| Spatial sampling | Full INCA 1 km grid (≈3,600 cells), optional `--coarsen N` | 3,363 points on a 5 km lattice (`austria_points_5km.csv`, EPSG:31287), nearest INCA 1 km cell each |
| API endpoint | `grid/historical/inca-v1-1h-1km` (NetCDF, 10-day chunks) | `timeseries/historical/inca-v1-1h-1km` (CSV, ~14 points per request) |
| Label stations | Innsbruck Univ., Innsbruck Airport, Steinach (crest: Patscherkofel) | 16 valley stations in 4 regions (see below) |
| Full run | a few minutes | ~255 requests, **~1–1.5 h** (API limit 240 req/h) |
| Disk (raw + outputs) | ~1.9 GB | ~0.7 GB raw + outputs |

## Features (per cell, hourly)

`T2M` 2 m temperature · `RH2M` relative humidity · `TD2M` dew point ·
`UU`/`VV` wind components · `P0` surface pressure · `GL` global radiation ·
`RR` precipitation · derived `wind_speed`, `wind_dir`.

## Labels — how "foehn" is defined

Foehn is detected at **valley stations**, not on the grid. It uses a
[foehnix](https://github.com/retostauffer/Rfoehnix)-style statistical model
(Plavcan & Mayr / Stauffer et al., Univ. Innsbruck):

1. 10-min station observations (`klima-v2-10min`) → hourly, labelled at the end
   of the hour so they line up with the INCA analysis time.
2. `dtheta` = potential temperature at the **crest** station − potential
   temperature at the valley station. Foehn mixes crest air down into the valley,
   so `dtheta` gets small.
3. Hours where the valley or crest wind is outside the station's **foehn wind
   sector** → `foehn_prob = 0`.
4. For the remaining hours, a 2-component Gaussian mixture on `dtheta`, with a
   logistic concomitant on relative humidity and wind speed, is fit by EM. The
   component with the lower mean is "foehn" → `foehn_prob`, and
   `foehn = foehn_prob ≥ 0.5`.
5. Each grid cell/point takes the label of its **nearest valley station**.
   Cells more than `--max-dist-km` (default 20 km) away stay unlabelled (NaN).

Regions in the Austria build:

| Region | Valley stations | Crest | Type |
|---|---|---|---|
| Tyrol | Innsbruck Univ., Innsbruck Airport, Steinach, Jenbach | Patscherkofel | south |
| Vorarlberg | Feldkirch, Dornbirn, Bludenz | Pitztaler Gletscher | south |
| Salzburg | Salzburg Airport, Bischofshofen, St. Johann, Bad Gastein, Rauris | Sonnblick | south |
| Carinthia / East Tyrol | Lienz, Obervellach, Döllach, Spittal/Drau | Sonnblick (north sector) | north |

**Known caveats** — check these before trusting the labels in an analysis:
- The wind sectors are defaults chosen from valley orientation and were **not
  tuned per station**.
- Vorarlberg uses a distant crest (Pitztaler Gletscher, ~95 km from Feldkirch), so its
  `dtheta` signal is weaker.
- Grid labels are nearest-station labels copied across space. They are not an
  independent per-cell detection, so treat spatial patterns in `foehn` with care.

## Outputs

Written to `data/<dataset>/` at the repo root. `data/` is gitignored, so share
the files outside git.

| File | Content |
|---|---|
| `raw/` | cached API responses. A crashed run can be restarted and skips finished chunks |
| `stations_hourly.parquet` | hourly station observations |
| `station_labels.parquet` | hourly `dtheta`, `foehn_prob`, `foehn` per valley station |
| `grid.nc` | `(time, y, x)` cube: all features + `foehn_prob`, `foehn`, `label_station`, `label_dist_km` |
| `grid_long.parquet` | long format, one row per (cell/point, hour). **This is the TiRex-2 input** |
| `points_with_labels.csv` | *(Austria only)* each point's assigned station, region and distance |

## Running

Run inside the project container (see the root README), or any Python 3.11+
environment with `requirements.txt` installed:

```bash
# quick API check, a few requests
python data_acquisition/tyrol_1km/build_dataset.py --probe
python data_acquisition/austria_5km/build_dataset_austria.py --probe

# full builds
python data_acquisition/tyrol_1km/build_dataset.py
python data_acquisition/austria_5km/build_dataset_austria.py

# options
--start 2025-10-01 --end 2026-10-01   # period (end exclusive)
--out <dir>                           # output dir (default data/<dataset>)
--max-dist-km 20                      # unlabelled beyond this distance
--coarsen 2                           # (Tyrol only) 2 km instead of 1 km
```

To reuse data that's already been downloaded, copy or move an existing output
folder (including `raw/`) to `data/tyrol_1km/` or `data/austria_5km/`, and the
builder will skip everything that's already cached.

## Attribution

Data: GeoSphere Austria, <https://data.hub.geosphere.at>, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Any figure or
submission that uses this data must credit "GeoSphere Austria".
