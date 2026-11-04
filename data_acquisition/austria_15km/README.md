# Austria 15 km — Phase I dataset

The [Austria 5 km build](../README.md) thinned out to a **15 km lattice: 378
points**, same hours (2025-10-01 → 2026-10-01) and same columns. It is the shared
dataset for Phase I, so both pairs forecast and evaluate at exactly the same
locations. One TiRex-2 run over all points takes about 15 s on CPU instead of
about 2 min for the 5 km grid.

Nothing is downloaded again. A point is kept if its Austria Lambert coordinates
(EPSG:31287, columns `x`, `y`) are both multiples of 15 km, i.e. every 3rd point
of the 5 km lattice in each direction.

## Getting the data

Download the archive from the release
[`data-austria-15km`](https://github.com/SandroMueller01/ai-vis-lab-2026/releases/tag/data-austria-15km)
(~70 MB). Run this in the repo root:

```bash
gh release download data-austria-15km --dir data
tar -xf data/austria_15km.tar -C data
```

## Rebuilding

Needs the Austria 5 km build in `data/austria_5km/`:

```bash
python data_acquisition/austria_15km/build_subset.py
python data_acquisition/events/build_events.py --data data/austria_15km
```

`--spacing-km 10` or `--spacing-km 20` gives other lattices (841 or 211
points); `--out` sets the output folder.

## Files (`data/austria_15km/`)

| File | Content |
|---|---|
| `grid_long.parquet` | one row per (point, hour), same columns as the 5 km build. **This is the TiRex-2 input** |
| `points_with_labels.csv` | the 378 points: `point_id` (same ids as the 5 km build), `x`, `y`, `lat`, `lon`, foehn station |
| `events.parquet`, `cold_wave_days.csv`, `fronts.csv` | [event labels](../events/README.md) for these points: cold drops, thunderstorms, cold fronts, cold-wave days |
| `stations_hourly.parquet`, `station_labels.parquet` | station data and foehn labels, copied unchanged |

The event labels are computed on the 378 points, so they differ slightly from
the 5 km build: 27 cold-wave days instead of 29 (the largest again on 2026-03-26,
98 % of the points at 13 UTC), and 16 cold fronts instead of 17 (14 of them the
same). How the cold fronts are defined, and why, is in
[`events/README.md`](../events/README.md#cold-fronts-definition-and-reasoning).

Data: GeoSphere Austria, <https://data.hub.geosphere.at>, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
