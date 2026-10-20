# Model Selection

Due: **28.10.2026, 23:59**. Register the final choice via the course's
model-selection form once the group has agreed.

> **Status: proposal.** Everything under *Task*, *Dataset* and *Decision* is a
> draft for the team to discuss. Comment on the PR, change what you disagree
> with, and we fill in the final decision once all four of us agree.

## Model

**TiRex-2** (NX-AI / JKU): a recurrent, xLSTM-based zero-shot time-series
forecasting foundation model. A single checkpoint handles univariate and
multivariate forecasting with optional past/future covariates, and it can
stream at constant per-patch cost.

- Paper: [arXiv:2607.01204](https://arxiv.org/abs/2607.01204)
- Code: [github.com/NX-AI/tirex-2](https://github.com/NX-AI/tirex-2)
- Weights: [huggingface.co/NX-AI/TiRex-2](https://huggingface.co/NX-AI/TiRex-2)
- Model type: probabilistic forecasting (quantile output), not a classifier.
  We use it zero-shot, with no fine-tuning.

## Task (proposal)

**Zero-shot forecasting of hourly alpine weather, and how TiRex-2 behaves when
the weather regime switches to foehn.**

Foehn is a warm, dry downslope wind in Alpine valleys. When it sets in,
temperature, humidity and wind change abruptly within a few hours. That makes
it a **real, labelled regime shift**. Every hour in our data has a
foehn / no-foehn label that comes from station observations and is independent
of the model input. So instead of injecting synthetic change points, we can ask
how a forecasting foundation model handles real ones.

Concretely, for each location and forecast origin:
- **Target:** one hourly variable, e.g. 2 m temperature `T2M` or wind speed.
  Pick one, maybe two.
- **Covariates:** the other INCA fields (humidity, dew point, wind
  components, pressure, radiation, precipitation).
- **Setup:** context of a few weeks of hourly history, horizon of e.g. 24 h,
  rolling origins over the year.

This framing covers what the two phases need:

| Phase | Questions it enables |
|---|---|
| **I: behavior** | Is forecast error higher during foehn than outside it, and in particular right at **onset** and **offset**? Are the quantiles calibrated during foehn, or overconfident? Do **covariates** help most exactly in foehn hours? How does it differ **across regions** and with **context length**? |
| **II: internals** | Do hidden states and gate activations **separate foehn from non-foehn** hours? The labels give a ready-made colouring for UMAP / k-NN in representation space. How does the recurrent state evolve patch by patch **around an onset**? Which input patches matter (saliency) when the model gets an onset right vs. wrong? |

It also combines three of the original candidate framings: covariates
(multivariate vs. univariate), regime shift, and context length / streaming.

## Dataset

Our own dataset, built from **GeoSphere Austria open data** (CC BY 4.0). It
covers **one year of hourly data, 2025-10-01 → 2026-10-01 (8,760 hours)**.
Everything about it is documented in
[`data_acquisition/README.md`](data_acquisition/README.md): source, API, label
method, caveats, and how to download or rebuild it.

| | Tyrol 1 km | Austria 5 km |
|---|---|---|
| Area | Innsbruck – Wipp valley – Brenner | All of Austria |
| Locations | 3,306 grid cells, **2,018 labelled** | 3,363 lattice points, **463 labelled** (Tyrol 122, Carinthia/East Tyrol 136, Salzburg 131, Vorarlberg 74) |
| Rows (location × hour) | 29.0 M | 29.5 M |
| Features | 8 INCA fields + derived wind speed/direction | same |
| Labels from | 3 valley stations, crest Patscherkofel | 16 valley stations in 4 regions |
| Foehn share | 9.2 % of station-hours (Innsbruck 6–7 %, Steinach 14 %) | 10.7 % (6–30 % per station) |

Why this data rather than a standard benchmark (GIFT-Eval / fev-bench):
- **Ground-truth regimes.** The labels let us split every result by
  "foehn / no foehn / onset", which a generic benchmark can't.
- **Large enough to be systematic.** Thousands of series and several hundred
  foehn hours per station over the year (≈540 in Innsbruck up to ≈2,650 in
  Bludenz), so patterns aren't cherry-picked.
- **Multivariate by nature,** so the covariate question is meaningful.
- **Local and checkable.** We know the region, and the label method is
  established foehn research from Innsbruck.

GIFT-Eval's weather subset remains an option as a **sanity reference**, to
check that TiRex-2 behaves as published on standard data before we interpret
anything on ours.

**Known limitations** (details in `data_acquisition/README.md`):
- The features are INCA analyses, which are model-assisted, not raw measurements.
- Grid labels are copied from the nearest valley station.
- Wind sectors are not tuned per station.
- Bludenz (30 %) and Salzburg Airport (16 %) have suspiciously high foehn
  shares. Check these before using them.

## Decision

Fill in once all four agree. The proposals are pre-filled.

- **Final task framing:** *proposal:* zero-shot forecasting of hourly alpine
  weather with covariates, analysed by foehn regime (especially onset/offset).
  → ☐ agreed
- **Target variable(s) and horizon:** *proposal:* `T2M` (+ maybe wind speed),
  24 h horizon. → ☐ agreed
- **Final dataset(s):** *proposal:* **Tyrol 1 km** as the main dataset (dense,
  best-validated labels), **Austria 5 km** for the cross-region comparison.
  → ☐ agreed
- **Scope:** *proposal:* single-model deep dive on TiRex-2, with GIFT-Eval
  weather as a sanity check only. → ☐ agreed
- **Registered on the course form:** ☐ (who, date)
