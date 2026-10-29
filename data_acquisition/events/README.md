# Event labels

Shared definitions of the weather events we analyse: **cold drops**, **thunderstorms**
and **cold-wave days**. Both pairs use the same files, so findings refer to the same
events and can be compared.

The labels are derived from the dataset itself (INCA `T2M` and `RR`). There are no
official event labels and no lightning data in the open data, so these are proxies.
The thresholds are a first draft (see [`model-selection.md`](../../model-selection.md))
and are command-line options, so the team can tune them in one place.

## Definitions

| Name | Definition (default) | Option |
|---|---|---|
| `dT24` | `T2M` minus `T2M` at the same hour the day before. Removes the daily cycle | |
| `dT1` | `T2M` minus `T2M` one hour before | |
| `cold_drop` | `dT24 ≤ −8 K` | `--cold-k` |
| `thunderstorm` | `dT1 ≤ −3 K` **and** `RR ≥ 2 mm` in the same hour | `--storm-k`, `--storm-rr` |
| cold-wave day | UTC day with an hour in which ≥ 25 % of all locations are in a `cold_drop` **at the same time** | `--cold-share` |
| episode | flagged hours of the same kind and location at most 6 h apart | `--episode-gap` |

Gaps in `T2M` of up to 3 h (`--max-gap`) are filled linearly per location before
the differences are taken. Longer gaps stay empty and never produce an event. In
the Austria 5 km build, 0.01 % of the `T2M` values are missing, almost all of them
in one hour (2025-10-10 09 UTC).

All times are UTC. The parquet files store time zone-aware timestamps, while
`grid.nc` stores naive timestamps that are also UTC.

## Running

Needs an existing dataset build (or the release download, see
[`../README.md`](../README.md)):

```bash
python data_acquisition/events/build_events.py                        # Austria 5 km
python data_acquisition/events/build_events.py --data data/tyrol_1km  # Tyrol 1 km
python data_acquisition/events/build_events.py --cold-k 6             # other threshold
```

## Outputs

Written next to the input, into `data/<dataset>/`:

| File | Content |
|---|---|
| `events.parquet` | one row per flagged location-hour: `point_id` (or `cell_id` for Tyrol), `time`, `kind`, `dT24`, `dT1`, `RR`, `episode` |
| `cold_wave_days.csv` | one row per UTC day: peak `share` of locations in a cold drop at the same hour, that hour (`peak_time`), `cold_wave` flag |

Austria 5 km, default thresholds: about 10 thunderstorm episodes per location and
year (80 % in May–August), about 29 cold-drop episodes per location and year, and
29 cold-wave days, the largest on 2026-03-26 (99 % of Austria at 13 UTC).

Example: onset times of all cold-drop episodes at one location (point 2798, Vienna).

```python
import pandas as pd

ev = pd.read_parquet("data/austria_5km/events.parquet")
drops = ev[ev.kind == "cold_drop"].groupby("episode").first()  # onset of each episode
onsets = drops[drops.point_id == 2798].time
```
