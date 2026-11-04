# Austria weather explorer (Phase I dashboard)

An interactive dashboard with several pages for exploring the hourly weather data over Austria and the behaviour of
TiRex-2 on it. It runs in the browser from static files, so it can be hosted on GitHub Pages. It is dark only.

**Every visualisation names the question(s) it answers** (the blue chips under its title, linking to the page of that
question). The five questions are the Phase I questions of the team:

1. How often does the system make mistakes?
2. In what situations is the system likely to be correct or incorrect?
3. How do we define a cold front?
4. What are the limitations of the system?
5. What kind of mistakes does it make? Regions, neighbours and start times.

## Pages and visualisations

| Page | Visualisation | Answers |
|---|---|---|
| **Explore the data** (`index.html`) | Map of the 15 km grid with a time slider, seven variables, event rings, point chart, jump-to buttons | supports Q3 (cold front, thunderstorm and cold drop rings) |
| **Q1** `q1.html` | Error by hours ahead: average error, share wrong by more than 2 °C, band coverage, against two simple forecasts | Q1, Q4 |
| | One forecast in detail: measured, forecast and 10–90 % band for any forecast and place | Q1, Q2 |
| **Q2** `q2.html` | Right and wrong by weather situation (16 situations), wrong share or band coverage | Q2, Q4 |
| | A calm day against a front day, side by side | Q2, Q1 |
| **Q3** `q3.html` | The rule in four steps | Q3 |
| | All 39 candidate fronts with the reason for each verdict | Q3 |
| | When the front reaches each point (map for the selected front) | Q3 |
| | The front as a diagonal (time against longitude) | Q3 |
| | What a detected front looks like (temperature, pressure, wind, rain) | Q3 |
| **Q4** `q4.html` | What the model does not see, and what we cannot check | Q4 |
| | How much better than "same as yesterday" | Q4, Q1 |
| | Error in normal weather and at weather events, by hours ahead | Q4, Q2 |
| | Is the uncertainty band honest? | Q4, Q2 |
| **Q5** `q5.html` | Error around the front arrival (mean error and band coverage) | Q5, Q4 |
| | Too warm or too cold? | Q5 |
| | Where is it wrong? (average error and bias map, regions) | Q5 |
| | Do points with more neighbours get better forecasts? | Q5 |
| | Does the start time matter? (start hour against hours ahead) | Q5 |

| **Carlos's findings** `carlos.html` | Carlos's 12 questions (C1 to C12) with his findings, as he reported them. Not computed by the dashboard | bears on Q1, Q2, Q4, Q5 |

**Who owns what.** Carlos works on his own list of questions (C1 to C12, for example "Can it forecast a cold front 6 h
ahead?" and "Is the 10–90 % band honest?"). The charts on the Q pages are Sandro's. Every chart shows an **Owner** line. Where a
chart overlaps with one of Carlos's questions it says so and links to his finding, and his card links back to the chart,
so that no question is answered twice in two places. The overlaps are: C4, C6, C8 and C9 with the front and band charts,
C5 with the limits, C7 with the events chart.

Each page starts with a short answer written from the data (the numbers are computed, not typed), and ends with its
sources. Every chart shows values on hover and has a table view (*Show as table*).

## Run it locally

```bash
python -m http.server -d phase1-model-behavior/pair-1/dashboard/site
```

Then open <http://localhost:8000>. The map libraries and the base map of the explore page come from the internet.

## Rebuild the data

The files in `site/data/` are generated and committed, so the site works from a plain checkout. Three steps, each
needs the output of the one before:

```bash
# 1. the TiRex-2 forecasts: about 75 minutes on a normal CPU, writes data/austria_15km/tirex2_forecasts.npz
docker compose run --rm lab python phase1-model-behavior/pair-1/run_forecasts.py
# 2. numbers for the question pages (results.json, forecast_runs.json, forecast_runs.bin)
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/build_results_data.py
# 3. observations for the explore page (obs/*.bin, meta.json, events.json)
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/build_dashboard_data.py
```

They need `data/austria_15km` (release `data-austria-15km`, with the event labels). Tests:

```bash
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/test_build_dashboard_data.py
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/test_build_results_data.py
```

What the forecasts are: for each of 336 start times and each of the 378 points, TiRex-2 got the last 28 days of
temperature of that point (nothing else) and forecast the next 24 hours. 306 start times are spread over the year (every
10 days, 9 start hours); 30 are 6 or 12 hours before the peak of a cold front. See `run_forecasts.py`.

The observations are stored in one byte per value (for example 0.27 K steps for temperature), the first hour as it is
and every later hour as the difference to the previous one (details in `build_dashboard_data.py`). The forecast runs
are stored in tenths of a degree (`build_results_data.py`). Together `site/data/` is about 31 MB, 14 MB compressed.

## Publish on GitHub Pages

The workflow [`.github/workflows/pages.yml`](../../../.github/workflows/pages.yml) publishes `site/` whenever it
changes on `main`. One-time setup: **Settings → Pages → Source: GitHub Actions**. The link then is
`https://sandromueller01.github.io/ai-vis-lab-2026/`.

## Plan

| Milestone | Content | Status |
|---|---|---|
| 1 | Explore page: map, day and hour slider, variables, event rings, point chart | done (PR #13) |
| 2 | Question pages Q1 to Q5 with the TiRex-2 results, a navigation and the questions named on every visualisation | done |
| 3 | Threshold explorer for the cold-front rule; forecasts with neighbours as input; Tyrol 1 km | open |
| 4 | Elevation per point and a 3D terrain view | open |
| 5 | Polish, saved views for the video | open |

## Credits

Data: GeoSphere Austria, <https://data.hub.geosphere.at>, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Model: [TiRex-2](https://github.com/NX-AI/tirex-2)
(Apache 2.0). Explore map: [MapLibre GL JS](https://maplibre.org), base map by CARTO, © OpenStreetMap contributors.
