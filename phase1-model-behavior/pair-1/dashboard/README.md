# Austria weather explorer (Phase I dashboard)

An interactive dashboard on the hourly weather over Austria and on how TiRex-2 forecasts it. It runs in the browser
from static files, so it can be hosted on GitHub Pages. It is dark only.

The dashboard has two pages with one shared menu: the main story and a page with further experiments. Each chapter
shows one figure that stays in place while text steps scroll past it (scrollytelling). Every chart shows values on
hover; the **i** buttons explain how to read a figure.

## Main story (`story.html`)

The page has three sections, the ones used in the presentation. **Section 1** is pinned and scrolling down moves its slides
**sideways**; after its last slide the page scrolls down. **Sections 2 and 3** are scrollytelling chapters: the text steps scroll
past on the left and the figure stays on the right. On screens narrower than about 900 px (or with `?flow=vertical`) section 1
is shown as a normal vertical stack. Everything else is on the second page, *Also tested*.

| Section | Content | Owner |
|---|---|---|
| **1 · The project** | The map (15 km grid, time slider, seven variables, event rings, point chart); the overview (4 weeks of hourly temperature at one point → TiRex-2, zero-shot → the next 24 hours with a 10–90 % band, repeated for all 378 points); *What are we testing, and how?* (the model, the data, our idea) | Sandro (map), Carlos (overview), both (idea) |
| **2 · Carlos's experiments** | Which hours it uses (each of the 672 history hours hidden once; the hours that matter repeat every 32 hours); copy or ignore a pattern (fixed Sundays); stranger history, wider band | Carlos |
| **3 · Sandro's experiments** | *How much better is it than "same as yesterday"?* (Limits) and *What happens when a cold front arrives?* (Errors: error and band coverage around the front arrival), each in steps; a link to *Also tested* | Sandro |

How it works: `story.js` builds section 1 (`hsection`) as a tall block with a pinned view whose sideways position follows the scroll
position. Sections 2 and 3 use `scrolly()`; Sandro's two chapters (`chapterBetter`, `chapterFront`) draw the line charts of
`charts.js` and redraw them with a marker for each step.

## Also tested (`also-tested.html`)

Also holds all other charts of Sandro's Limits and Errors sections and of the questions *How often it is wrong*, *When it is right or wrong* and *Finding cold fronts*.

| Section | Content | Owner |
|---|---|---|
| Does more information help? | Longer history, time inputs, extra variables (pressure, humidity, wind, upwind points) | Carlos |
| History before a cold front | The history heatmap for random forecasts and for forecasts before a cold front | Carlos |
| Sunday switch | How different the repeated Sundays must be before the model copies them | Carlos |
| Where the strange part sits | Does it matter where in the history the strange part is? | Carlos |
| Catching up, lasting cold, honest band | Once the model sees the front, does it catch up? Does it expect the cold to last? Does it know when it is unsure? | Carlos |
| Time curve | How a cold front changes Austria's weather | Carlos |
| How often it is wrong | Error by hours ahead; one forecast in detail | Sandro |
| When it is right or wrong | Right and wrong by weather situation; a calm day against a front day | Sandro |
| Finding cold fronts | The rule in four steps; all candidate fronts; arrival map; the front as a diagonal; what a detected front looks like | Sandro |
| Explore it yourself | Every cold front: which points the forecast missed and where | Carlos |

The code: `story.js` (chapters and page layout), `pages.js` (Sandro's sections), `app.js` (map), `common.js` (menu
`STORY_TABS`, helpers), `charts.js`. `index.html` only forwards to `story.html`, so the plain site link opens the
story. `q1.html` to `q5.html` and `carlos.html` are the earlier multi-page version and are no longer linked from the menu.

## Run it locally

```bash
python -m http.server -d phase1-model-behavior/pair-1/dashboard/site
```

Then open <http://localhost:8000/story.html>. The map libraries and the base map come from the internet.

## Rebuild the data

The files in `site/data/` are generated and committed, so the site works from a plain checkout. Steps 1 to 3 each
need the output of the one before; step 4 only needs Carlos's experiment results:

```bash
# 1. the TiRex-2 forecasts: about 75 minutes on a normal CPU, writes data/austria_15km/tirex2_forecasts.npz
docker compose run --rm lab python phase1-model-behavior/pair-1/run_forecasts.py
# 2. numbers for Sandro's sections (results.json, forecast_runs.json, forecast_runs.bin)
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/build_results_data.py
# 3. observations for the map (obs/*.bin, meta.json, events.json)
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/build_dashboard_data.py
# 4. Carlos's charts (site/data/carlos/*.json), from his saved experiment results in data/notebooks/results/
docker compose run --rm lab python phase1-model-behavior/pair-1/dashboard/build_carlos_data.py
```

Steps 1 to 3 need `data/austria_15km` (release `data-austria-15km`, with the event labels). Tests:

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
changes on `main`. One-time setup: **Settings → Pages → Source: GitHub Actions**. The dashboard is then at
`https://sandromueller01.github.io/ai-vis-lab-2026/story.html`.

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
(Apache 2.0); TiRex logo (`site/tirex.svg`) from the same repository, by NX-AI. Map:
[MapLibre GL JS](https://maplibre.org), base map by CARTO, © OpenStreetMap contributors.
