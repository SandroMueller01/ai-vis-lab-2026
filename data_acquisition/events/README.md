# Event labels

Shared definitions of the weather events we analyse: **cold drops**, **thunderstorms**,
**cold fronts** and **cold-wave days**. Both pairs use the same files, so findings
refer to the same events and can be compared.

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
| passage | at one location: `T2M` change over 3 h ≤ −3 K **and** `P0` change over the 6 h around it ≥ +2 hPa, both as anomalies from the usual change at that location, month and hour of day | `--front-k`, `--front-hpa` |
| front | ≥ 50 % of all locations have a passage within 24 h, **and** the passage times fit a line moving across the area: plane fit R² ≥ 0.3, speed 1–30 m/s, moving towards 60–240° (coming from the west or north) | `--front-share`, `--front-r2` |
| `cold_front` | a passage that belongs to a front | |
| episode | flagged hours of the same kind and location at most 6 h apart | `--episode-gap` |

`cold_drop` and `cold_front` answer different questions. A cold drop says that it
is much colder than yesterday at the same hour, whatever the reason. A cold front
says *when* a colder air mass arrives at a location. On 2026-03-25/26 the front
passes Vienna around 20 UTC on the 25th, while the cold drops peak at 13 UTC on
the 26th, the first afternoon in the cold air. Why the front is defined this way
is explained in [Cold fronts: definition and reasoning](#cold-fronts-definition-and-reasoning).

Gaps in `T2M` and `P0` of up to 3 h (`--max-gap`) are filled linearly per location before
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
| `fronts.csv` | one row per candidate front: `peak_time`, `share` of locations with a passage, plane fit (`r2`, `speed_ms`, `moves_to_deg`), `cold_front` flag. Rejected candidates are kept, so you can see why they failed |

`kind` in `events.parquet` is `cold_drop`, `thunderstorm` or `cold_front`.

Austria 5 km, default thresholds: about 10 thunderstorm episodes per location and
year (80 % in May–August), about 29 cold-drop episodes per location and year, 29
cold-wave days, the largest on 2026-03-26 (99 % of Austria at 13 UTC), and 17
cold fronts (40 candidates), e.g. 2026-03-26 01 UTC, 2026-05-11 21 UTC and
2026-07-01 06 UTC.

Example: onset times of all cold-drop episodes at one location (point 2798, Vienna).

```python
import pandas as pd

ev = pd.read_parquet("data/austria_5km/events.parquet")
drops = ev[ev.kind == "cold_drop"].groupby("episode").first()  # onset of each episode
onsets = drops[drops.point_id == 2798].time
```

## Cold fronts: definition and reasoning

A cold front is the leading edge of a colder air mass: a narrow zone where the
temperature changes sharply, moving so that cold air replaces warm air. There is
no official list of cold fronts for Austria in the open data, so we detect them
ourselves. Research uses three kinds of evidence:

1. **Thermal fronts**: the strongest gradient of (wet-bulb or equivalent)
   potential temperature at about 850 hPa (Renard & Clarke 1965; Hewson 1998).
   Jenkner et al. (2010) built a front climatology for the Alps this way and
   found that cold fronts slow down in front of the mountains. We cannot use this
   directly: INCA has surface fields only.
2. **Wind shift**: the 10 m wind turning from a southerly to a northerly
   component within 6 h (Simmonds et al. 2012). Schemm et al. (2015) found this
   works best for long, north–south oriented moving fronts.
3. **Station signature**: when a cold front passes a station, the temperature
   falls, the pressure rises after falling beforehand, the wind veers and it often
   rains. Mesonet studies combine pressure rise and temperature drop into one score.

Our definition combines (3) at each location with the defining property of (1),
a line that moves across the area:

- **Temperature and pressure, not wind.** Wind in the Alpine valleys follows the
  valley (e.g. the Inn valley), so a wind shift is not reliable there. We keep wind
  for checking the result instead (see below).
- **Anomalies.** The 3 h `T2M` change and the 6 h `P0` change are compared with the
  usual change at the same location, month and hour of day. Without this, every
  evening cooling and the daily pressure tide (about 1 hPa) would count.
- **Thresholds −3 K / +2 hPa.** Chosen by comparing calm days (no events, no rain,
  e.g. 2026-08-13, 2026-03-20) with the largest cooling events, on the 15 km grid:

  | Passage thresholds | Passages per location and year | Share of locations on calm days | On the largest events |
  |---|---|---|---|
  | −2 K / +1 hPa | 152 | up to 43 % | 79–100 % |
  | −3 K / +1 hPa | 81 | up to 17 % | 74–100 % |
  | **−3 K / +2 hPa** | **60** | **up to 6 %** | **66–100 %** |
  | −4 K / +2 hPa | 35 | up to 1 % | 56–99 % |

- **A front covers the country and moves.** A thunderstorm gust front also brings
  sudden cooling and a pressure jump, but only locally. So ≥ 50 % of the locations
  need a passage within 24 h, and the passage times must fit a plane, i.e. a
  straight line moving at constant speed. R² ≥ 0.3 rejects cases where the country
  cools at random times or all at once (e.g. 2025-10-23, 89 % of the locations
  but R² 0.05). Fronts reaching Austria come from the west or north, hence the
  direction 60–240°.

**Checks.** Wind and rain are not part of the definition, so they can serve as an
independent check. At the start of `cold_front` passages (Austria 15 km), the
wind turns towards north (mean `VV` over 3 h drops by ≥ 1 m/s) in 38 % of the
cases against 17 % of all hours, and it rains (≥ 0.5 mm within ±3 h) in 77 %
against 14 %. The dew point shows no signal (falls by ≥ 1 K in 31 % against 29 %).
The 5 km and 15 km grids find 17 and 16 fronts, 14 of them the same; the others
are close to the R² threshold. On 2026-03-25 at Vienna the signature is textbook:
within about 4 h `T2M` −9.6 K, `P0` +4.6 hPa, wind from south to northwest.

**Limitations.**
- **Almost no winter fronts** (none from November to early March). Cold air
  pooling in valleys and basins decouples the surface from the air mass above, so
  the surface signature is weak. Phase I analyses of fronts are therefore about
  spring to autumn.
- **Summer squall lines** (organised lines of thunderstorms) also move as a line
  and can pass as a front. Without upper-air data we cannot separate them.
- `speed_ms` and `moves_to_deg` come from a plane fit over all of Austria. The
  Alps slow fronts down and bend them, so the speed is a rough summary, not the
  speed of the front at any one place.
- The thresholds are tuned on this one year by us, and there is no independent
  front list to validate against. A useful next check would be a few dates
  against published weather charts.

**References**
- Renard, R. J., and L. C. Clarke (1965): Experiments in numerical objective
  frontal analysis. *Mon. Wea. Rev.* 93, 547–556.
- Hewson, T. D. (1998): Objective fronts. *Meteorol. Appl.* 5, 37–65.
- Jenkner, J., M. Sprenger, I. Schwenk, C. Schwierz, S. Dierer and D. Leuenberger
  (2010): Detection and climatology of fronts in a high-resolution model
  reanalysis over the Alps. *Meteorol. Appl.* 17, 1–18.
  [ETH Research Collection](https://www.research-collection.ethz.ch/handle/20.500.11850/16922)
- Simmonds, I., K. Keay and J. A. T. Bye (2012): Identification and climatology of
  Southern Hemisphere mobile fronts in a modern reanalysis. *J. Climate* 25, 1945–1962.
- Schemm, S., I. Rudeva and I. Simmonds (2015): Extratropical fronts in the lower
  troposphere – global perspectives obtained from two automated methods.
  *Q. J. R. Meteorol. Soc.* 141, 1686–1698. [BORIS](https://boris.unibe.ch/71843)
