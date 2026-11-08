# ai-vis-lab-2026

JKU *AI and Visualization* (WS 2026/27) lab assignment: Vis4AI analysis of a
model's behavior (Phase I, black-box) and learned representations (Phase II,
white-box), with an AI4Vis comparison of AI-aided vs. human-only analysis
pipelines.

## Model

**[TiRex-2](https://github.com/NX-AI/tirex-2)** — a recurrent, xLSTM-based
zero-shot time-series forecasting foundation model from
[NX-AI](https://www.nx-ai.com/en/tirex-2) (Sepp Hochreiter's group, JKU).
Released July 2026, accepted as an Oral at NeurIPS 2026. Single checkpoint
handles both univariate and multivariate forecasting directly from history,
optionally conditioned on past/future covariates, with constant per-patch
inference cost under streaming. Evaluated zero-shot on the
[GIFT-Eval](https://huggingface.co/spaces/Salesforce/GIFT-Eval) and
[fev-bench](https://github.com/autogluon/fev) leaderboards.

- Paper: [arXiv:2607.01204](https://arxiv.org/abs/2607.01204)
- Code: [github.com/NX-AI/tirex-2](https://github.com/NX-AI/tirex-2)
- Weights: [huggingface.co/NX-AI/TiRex-2](https://huggingface.co/NX-AI/TiRex-2)
- License: Apache 2.0

```bash
pip install tirex-2
```

```python
from tirex2 import load_model
model = load_model("NX-AI/TiRex-2", device="cpu")
forecast = model.forecast([ts], prediction_length=32, output_type="numpy")[0]
```

A timely, locally-relevant pick for this course: it's a recent xLSTM-based
foundation model from a JKU-adjacent lab, with a real architectural story
(recurrent gating, not attention) that gives Phase II something genuinely
different to visualize than yet another transformer's attention maps.

## Task

Forecast hourly temperature at points sampled from a 5 km grid covering all of
Austria. Starting with each location's own temperature history, then adding
its local weather variables, and then the temperatures of neighbouring points,
especially upstream (west) ones. We test whether this extra information
improves the forecasts and helps detect thunderstorms and cold fronts earlier.

Details, reasoning and the dataset are in
[`model-selection.md`](model-selection.md) and [Data](#data).

## Team

**Team name: XPL41N**

| Name | Matriculation no. | GitHub | Pair |
|---|---|---|---|
| Sandro Müller | K52010874 | [@SandroMueller01](https://github.com/SandroMueller01) | Pair 1 |
| Carlos Elizondo | K52320897 | [@erca-2064](https://github.com/erca-2064) | Pair 1 |
| Nikolas Basios | K12323568 | [@nklsb](https://github.com/nklsb) | Pair 2 |
| Maximilian Fridrich | K01608851 | [@maximilianfridrich](https://github.com/maximilianfridrich) | Pair 2 |

Pair 1 is **AI-aided in Phase I** and human-only in Phase II. Pair 2 is the
reverse (see [Assignment structure](#assignment-structure)).

## Assignment structure

Two phases, each investigated independently by both pairs, who then compare
notes. The pairs swap AI4Vis roles between phases.

| Phase | Pair 1 | Pair 2 |
|---|---|---|
| **Phase I** — How does the model behave? | AI-aided | Human-only |
| **Phase II** — What did the model learn? | Human-only | AI-aided |

- **Phase I (black-box behavior)**: `phase1-model-behavior/pair-1/`,
  `phase1-model-behavior/pair-2/` — how TiRex-2's temperature forecasts behave,
  seen only from inputs and outputs: where and when they fail, how they react
  to cold drops and thunderstorms, whether the forecast bands are calibrated,
  and whether local variables and upstream points change the forecast at all.
  Both pairs use the Austria 15 km dataset (378 points) and the shared
  [event labels](data_acquisition/events/README.md), on enough locations and
  events that any pattern is systematic, not cherry-picked. Synthetic inputs
  (e.g. an inserted temperature drop) are used to test specific hypotheses.
- **Phase II (opening the black box)**: `phase2-model-internals/pair-1/`,
  `phase2-model-internals/pair-2/` — xLSTM internals, following up on the
  Phase I findings: e.g. whether the hidden state changes before a cold drop,
  how covariates are encoded compared with the target, and how
  representations differ between good and poor forecasts. At least two
  techniques per pair (e.g. hidden-state projections/UMAP, gate-activation
  heatmaps, gradient-based saliency over input patches, k-NN in
  representation space), compared or combined rather than shown in isolation.
- **AI interactions**: `ai-interactions/` — one log per
  (phase, AI-aided pair), documenting key prompts, which suggestions were
  accepted/modified/rejected and why, observed failure patterns, and emerging
  best practices. Required only from whichever pair is AI-aided in that phase.
- **AI reflection**: `ai_reflection_midpoint.md` — the AI-aided pair's
  reflection on Phase I with GenAI, starting with their names and student IDs.
- **Submissions**: `submissions/midpoint/` (end of Phase I: code from both
  pairs + AI log + up to 5-minute progress video) and `submissions/final/`
  (end of Phase II: code from both pairs + AI logs from both phases +
  10-minute presentation + slide deck).

## Key dates

| Deadline | Date |
|---|---|
| Group formation | 21.10.2026, 23:59 |
| Task selection | 28.10.2026, 23:59 |
| Midpoint submission (end of Phase I) | 11.11.2026, 23:59 |
| Final submission (end of Phase II) | 09.12.2026, 23:59 |
| Written on-site exam | 17.12.2026 |
| Written on-site retry exam | 18.02.2027 |

## Midpoint submission (Phase I, 11.11.2026, 23:59)

Everything for the midpoint is in this repository. The checklist and the video link are in
[`submissions/midpoint/README.md`](submissions/midpoint/README.md).

| Part | Where |
|---|---|
| Code of both pairs | this repository, branch `main` |
| Pair 1 (AI-aided in Phase I) | [`phase1-model-behavior/pair-1/`](phase1-model-behavior/pair-1/): forecast runs, dashboard, experiment notebooks |
| Pair 2 (human-only in Phase I) | [`phase1-model-behavior/pair-2/`](phase1-model-behavior/pair-2/) |
| AI interaction log | [`ai-interactions/phase1-ai-aided-pair.md`](ai-interactions/phase1-ai-aided-pair.md) |
| AI reflection | [`ai_reflection_midpoint.md`](ai_reflection_midpoint.md) |
| Cross-pair comparison | [`phase1-model-behavior/comparison.md`](phase1-model-behavior/comparison.md) |
| Dashboard (live) | <https://sandromueller01.github.io/ai-vis-lab-2026/> |
| Progress video (2:48 min, limit 5) | linked in [`submissions/midpoint/README.md`](submissions/midpoint/README.md); the video file is not in git |

## Data

Hourly multivariate weather time series for Austria, built from GeoSphere
Austria open data (CC BY 4.0), with shared labels for cold drops, cold waves
and thunderstorms (and foehn as extra context). See
[`data_acquisition/README.md`](data_acquisition/README.md) for the datasets,
where they come from, how the labels are defined, and how to rebuild them.

**Get the data:** download the ready-made datasets (~3 GB) from the release
[`data-2025-26`](https://github.com/SandroMueller01/ai-vis-lab-2026/releases/tag/data-2025-26).
Run this in the repo root:

```bash
gh release download data-2025-26 --dir data
tar -xf data/tyrol_1km.tar -C data
tar -xf data/austria_5km.tar -C data
```

You then have `data/tyrol_1km/` and `data/austria_5km/`, and you can delete the
two `.tar` files. You need the [GitHub CLI](https://cli.github.com) (`gh`),
logged in with `gh auth login`. Without it, download the two `.tar` files from
the release page in the browser into `data/` and run the same two `tar`
commands. `data/` is gitignored, so never commit datasets. Share them through
the release instead.

**Phase I dataset (15 km):** both pairs work with the same 378 points, a
thinned-out version of the 5 km dataset with the event labels already
calculated (about 70 MB), from the release
[`data-austria-15km`](https://github.com/SandroMueller01/ai-vis-lab-2026/releases/tag/data-austria-15km):

```bash
gh release download data-austria-15km --dir data
tar -xf data/austria_15km.tar -C data
```

How it is made and what is in it:
[`data_acquisition/austria_15km/README.md`](data_acquisition/austria_15km/README.md).

## Dashboard

An interactive dashboard for the Phase I analysis: a map of the data with a
time slider, then a scrollytelling story of how TiRex-2 reads its history and
where it fails, and a second page with further experiments.

- Live: <https://sandromueller01.github.io/ai-vis-lab-2026/story.html>
- Run it locally: `python -m http.server -d phase1-model-behavior/pair-1/dashboard/site`, then open <http://localhost:8000/story.html>
- How it works and how to rebuild the data:
  [`phase1-model-behavior/pair-1/dashboard/README.md`](phase1-model-behavior/pair-1/dashboard/README.md)

## Setup

Everyone works in the same Docker image (Python 3.12, CPU torch, TiRex-2).
Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), then
use one of these:

**VS Code (recommended):** install the *Dev Containers* extension, open the
repo, then run *Dev Containers: Reopen in Container*.

**Terminal:**

```bash
docker compose up                       # JupyterLab on http://localhost:8888
docker compose run --rm lab python data_acquisition/tyrol_1km/build_dataset.py
```

The repo is live-mounted at `/workspace`, so edits on your machine show up in
the container right away. Rebuild (`docker compose build`) only after changing
`requirements.txt` or the `Dockerfile`.

Without Docker: use Python ≥ 3.11 (needed by `tirex-2`), then
`pip install -r requirements.txt`.

## Contributing

Branch → pull request → one review → merge. See
[`WAYS_OF_DEV_WORKING.md`](WAYS_OF_DEV_WORKING.md) for branch names, commit
prefixes and the review process.

## Repository layout

```
ai-vis-lab-2026/
├── model-selection.md          # model, task, dataset
├── data_acquisition/           # GeoSphere weather dataset builders
│   ├── tyrol_1km/
│   ├── austria_5km/
│   ├── austria_15km/           # Phase I dataset: every 3rd point of the 5 km one
│   └── events/                 # shared event labels (cold drops, cold fronts, thunderstorms)
├── scripts/                    # shared helpers, e.g. tirex_smoke_test.py
├── notebooks/                  # shared exploratory notebooks
├── phase1-model-behavior/
│   ├── pair-1/                 # incl. dashboard/ (published on GitHub Pages)
│   └── pair-2/
├── phase2-model-internals/
│   ├── pair-1/
│   └── pair-2/
├── ai-interactions/             # GenAI interaction logs (AI-aided pair)
│   ├── phase1-ai-aided-pair.md
│   └── phase2-ai-aided-pair.md
├── ai_reflection_midpoint.md   # Phase I reflection on GenAI (AI-aided pair)
├── team-info.json, workload.json   # course-required team files
├── submissions/
│   ├── midpoint/
│   └── final/
├── data/                       # gitignored; raw/intermediate datasets
├── .github/                    # PR template, CI and Pages workflows
├── .devcontainer/              # VS Code dev container
├── Dockerfile
└── docker-compose.yml
```
