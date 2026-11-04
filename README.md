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

| Role | Name |
|---|---|
| Member 1 (Pair 1) | TBD |
| Member 2 (Pair 1) | TBD |
| Member 3 (Pair 2) | TBD |
| Member 4 (Pair 2) | TBD |

Team name: TBD

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
  Both pairs use the Austria 5 km data and the shared
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
- **AI interaction logs**: `ai-interaction-logs/` — one log per
  (phase, AI-aided pair), documenting key prompts, which suggestions were
  accepted/modified/rejected and why, observed failure patterns, and emerging
  best practices. Required only from whichever pair is AI-aided in that phase.
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
│   └── events/                 # shared event labels (cold drops, thunderstorms)
├── scripts/                    # shared helpers, e.g. tirex_smoke_test.py
├── notebooks/                  # shared exploratory notebooks
├── phase1-model-behavior/
│   ├── pair-1/
│   └── pair-2/
├── phase2-model-internals/
│   ├── pair-1/
│   └── pair-2/
├── ai-interaction-logs/
│   ├── phase1-ai-aided-pair.md
│   └── phase2-ai-aided-pair.md
├── submissions/
│   ├── midpoint/
│   └── final/
├── data/                       # gitignored; raw/intermediate datasets
├── .github/                    # PR template, CI workflows
├── .devcontainer/              # VS Code dev container
├── Dockerfile
└── docker-compose.yml
```
