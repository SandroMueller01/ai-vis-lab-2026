# Austria weather explorer (Phase I dashboard)

An interactive map of the hourly weather over Austria, for exploring the data we use for TiRex-2 and the
events we label in it. It runs in the browser from static files, so it can be hosted on GitHub Pages.

**What it shows now (milestone 1):** the INCA analysis on the 15 km grid for one year, as a map with a time slider.

- Variables: temperature, dew point, humidity, sea-level pressure, wind speed, global radiation, rain.
- Event rings: cold front passages, thunderstorms and cold drops (definitions in
  [`data_acquisition/events/README.md`](../../../data_acquisition/events/README.md)).
- A year overview above the slider (cold fronts on top, thunderstorms below). Click or drag to jump.
- Click a point for a chart of the selected variable, three days before and after, with the event hours marked.
- "Jump to": the three largest cold fronts, the widest thunderstorm day and a calm day.
- Zoom and pan, light and dark map, play button, and a link that remembers the view
  (`#v=T2M&t=4233&ev=cold_front&sel=300`).

## Run it locally

```bash
python -m http.server -d phase1-model-behavior/pair-1/dashboard/site
```

Then open <http://localhost:8000>. The map libraries and the base map come from the internet.

## Rebuild the data

The files in `site/data/` are built from the [Austria 15 km dataset](../../../data_acquisition/austria_15km/README.md)
(including its event labels), so they only need to be rebuilt if that dataset changes:

```bash
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/build_dashboard_data.py
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/test_build_dashboard_data.py
```

Each variable is one file `site/data/obs/<VAR>.bin` (about 3.3 MB). The values are stored in one byte
(for example 0.27 K steps for temperature), the first hour as it is and every later hour as the difference to the
previous one. This keeps the whole year at about 12 MB in git. Details are in the docstring of
`build_dashboard_data.py`.

## Publish on GitHub Pages

The workflow [`.github/workflows/pages.yml`](../../../.github/workflows/pages.yml) publishes `site/` whenever it
changes on `main`. One-time setup: **Settings → Pages → Source: GitHub Actions**. The link then is
`https://sandromueller01.github.io/ai-vis-lab-2026/`.

## Plan

| Milestone | Content | Status |
|---|---|---|
| 1 | Map, time slider, variables, event rings, point chart, year overview | done |
| 2 | TiRex-2 layers: median, q10–q90 band, error; lead-time and forecast-run mode | open |
| 3 | Zoom levels: 5 km for event windows, Tyrol 1 km | open |
| 4 | Elevation per point and a 3D terrain view | open |
| 5 | Polish, saved views for the video | open |

## Credits

Data: GeoSphere Austria, <https://data.hub.geosphere.at>, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Map: [MapLibre GL JS](https://maplibre.org),
base map by CARTO, © OpenStreetMap contributors.
