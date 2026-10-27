# Data acquisition — Austrian hourly weather datasets

Two builders that download hourly weather fields from the
[GeoSphere Austria Data Hub](https://data.hub.geosphere.at) (CC BY 4.0). The
outputs are multivariate hourly time series, one per location, which is the
input shape for TiRex-2.

What we use them for (see [`model-selection.md`](../model-selection.md)):
forecasting the temperature change with TiRex-2, and checking how well it
handles **cold drops, cold waves and thunderstorms** moving across Austria.
These events are labelled by a separate step, [`events/`](events/README.md),
so that both pairs use the same definitions.

The builders also attach a **foehn / no-foehn label** to every location and
hour. That was the focus of the first data version. It's no longer the main
question, but it stays in the data as extra context: foehn often ends with a
cold front.

Both default to the period **2025-10-01 → 2026-10-01** (one year, 8,760 hours).

| | `tyrol_1km/` | `austria_5km/` |
|---|---|---|
| Area | Innsbruck – Wipp valley – Brenner (bbox 46.95–47.45 N, 11.00–11.75 E) | All of Austria |
| Spatial sampling | Full INCA 1 km grid (≈3,600 cells), optional `--coarsen N` | 3,363 points on a 5 km lattice (`austria_points_5km.csv`, EPSG:31287), nearest INCA 1 km cell each |
| API endpoint | `grid/historical/inca-v1-1h-1km` (NetCDF, 10-day chunks) | `timeseries/historical/inca-v1-1h-1km` (CSV, ~14 points per request) |
| Label stations | Innsbruck Univ., Innsbruck Airport, Steinach (crest: Patscherkofel) | 16 valley stations in 4 regions (see below) |
| Full run (measured 2026-10-24) | **3 min 19 s** | **49 min 45 s** (249 requests) |
| Disk (raw + outputs) | ~1.9 GB | ~0.7 GB raw + outputs |

## Getting the data (fast)

You don't need to rebuild anything. The finished outputs (without the `raw/`
download cache) are attached to the GitHub release
[`data-2025-26`](https://github.com/SandroMueller01/ai-vis-lab-2026/releases/tag/data-2025-26),
one archive per dataset:

```bash
gh release download data-2025-26 --dir data
tar -xf data/tyrol_1km.tar -C data
tar -xf data/austria_5km.tar -C data
```

This gives you `data/tyrol_1km/` and `data/austria_5km/`, exactly as the
builders write them. Delete the `.tar` files afterwards. `tar` comes with
Windows 10+, macOS and Linux. Without `gh`, download the two files from the
release page in the browser.

Rebuild from the API (see [Running](#running)) only if you need a different
period, area or label setting.

### Measured default builds (2026-10-24)

One full run of each builder with an empty local download cache, using the default
2025-10-01 to 2026-10-01 period, variables, spatial sampling and label settings.

| Stage | Tyrol 1 km | Austria 5 km |
|---|---|---|
| Station acquisition | 13.0 s | 53.0 s |
| Grid acquisition | 2 min 30 s | 47 min 12 s |
| Both acquisition stages | 2 min 43 s | 48 min 5 s |
| Station foehn labelling | 0.07 s | 0.32 s |
| Attach labels and write outputs | 35 s | 1 min 39 s |
| Complete build, including startup | 3 min 19 s | 49 min 45 s |
| Successful HTTP requests | 41 | 249 |

## Where the data comes from

| | |
|---|---|
| Provider | [GeoSphere Austria](https://www.geosphere.at) (formerly ZAMG), the Austrian national weather and geological service |
| Portal | [GeoSphere Austria Data Hub](https://data.hub.geosphere.at): open data, no account or API key needed |
| Gridded features | [INCA analysis — large domain](https://data.hub.geosphere.at/dataset/inca-v1-1h-1km) (`inca-v1-1h-1km`): hourly, 1 km, EPSG:31287, available from 2011-03-15 |
| Station observations | [Stationsdaten v2, 10 min](https://data.hub.geosphere.at/dataset/klima-v2-10min) (`klima-v2-10min`): quality-controlled 10-min observations of the Austrian station network |
| Access | [Dataset API v1](https://dataset.api.hub.geosphere.at/v1/docs), endpoints `grid/historical`, `timeseries/historical` and `station/historical`. Limits: 5 requests/s, 240 requests/h, max. 1M values per CSV and 10M per NetCDF request. The builders split their requests to stay under these limits |
| Downloaded | 2026-10-20, with the scripts in this folder. Since then only output paths and code style have changed, not the download or labelling logic |
| License | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): free to use and share, attribution required (see below) |

INCA is GeoSphere's operational nowcasting analysis. It combines station
observations, remote sensing and NWP model output into a gridded field. Our
features are therefore model-assisted analyses, not raw measurements. The
foehn **labels** are derived only from station observations (see below), so
features and labels come from different sources.

The labelling follows the statistical foehn diagnosis developed at the
University of Innsbruck:
- D. Plavcan, G. J. Mayr, A. Zeileis (2014): *Automatic and probabilistic foehn
  diagnosis with a statistical mixture model.* J. Appl. Meteor. Climatol. 53, 652–659.
- R. Stauffer et al.: [`foehnix`](https://github.com/retostauffer/Rfoehnix) R
  package. Our labelling is a compact Python re-implementation of this idea, not
  the package itself.

## Features (per cell, hourly)

`T2M` 2 m temperature · `RH2M` relative humidity · `TD2M` dew point ·
`UU`/`VV` wind components · `P0` mean sea level pressure · `GL` global radiation ·
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
| `events.parquet`, `cold_wave_days.csv` | event labels, written by [`events/build_events.py`](events/README.md) (not by the builders) |

**Time stamps** are UTC everywhere and mark the end of the hour (INCA analysis
time). The parquet files store them time zone-aware (`datetime64[us, UTC]`), so
filter with UTC timestamps, e.g. `pd.Timestamp("2026-03-26", tz="UTC")`.
`grid.nc` stores naive timestamps that are also UTC.

**Gaps:** every location has all 8,760 hours, but a few values are NaN
(Austria 5 km: 0.01 % of `T2M`, almost all in one hour, 2025-10-10 09 UTC). The
event labels fill `T2M` gaps of up to 3 h and leave longer gaps empty. Do the
same in an analysis, so results stay comparable.

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
