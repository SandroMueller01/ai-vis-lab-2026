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

**Forecasting temperature change with TiRex-2, and whether input from
multiple stations makes it better at it. The end goal is to detect
thunderstorms and cold waves moving across Austria early.**

Step by step:

1. **Temperature forecast at a location.** TiRex-2 forecasts the hourly 2 m
   temperature `T2M` zero-shot, for e.g. the next 6–24 h. What matters is the
   **change** (ΔT), not the absolute level.
2. **Add more input, step by step**, and measure what each step adds:
   - (a) only the location's own temperature history (univariate)
   - (b) plus the location's other variables (humidity, wind, pressure,
     precipitation, radiation)
   - (c) plus the **temperature series of other locations**, especially those
     **upstream**, i.e. west or northwest, where fronts usually come from
3. **From forecast to event.** We check whether the forecast ΔT is good enough
   to flag a **cold wave** or **thunderstorm** in time, scored as an event
   forecast: hit rate, false alarms, lead time.

We have no official event labels, so we define the events from the data
itself, as rules to tune together:

| Event | Proxy definition (draft) | Frequency in our year |
|---|---|---|
| **Thunderstorm** | ≥ 3 K drop within 1 h **and** ≥ 2 mm rain in that hour | ≈ 10 events per location per year, almost all **May–August** |
| **Cold wave / cold front** | ≥ 8 K colder than the same hour the day before | **29 days** on which ≥ 25 % of Austria is affected |

A first check shows that the strongest cold wave (2026-03-26, 99 % of
Austria) moves clearly **from west to east**: the time of the temperature drop
correlates with longitude at r = 0.82, ≈ 87 km/h. For the other large events
this simple measurement shows no clear direction. Fronts don't always come
from the west, and the daily temperature cycle interferes with the
measurement. **Whether, and how much, upstream stations really help is
therefore an open question,** which makes it a good one for Phase I.

How it maps to the phases:

| Phase | Questions it enables |
|---|---|
| **I: behavior** | How well does TiRex-2 forecast ΔT, especially **right before and during** an event? How much do steps (b) and (c) add, and does it depend on **wind direction**, i.e. are the extra stations actually upstream? Are the quantiles calibrated at events, or overconfident? How far ahead are events detectable? How does it differ by region, season, and context length? |
| **II: internals** | Does the model's internal state change **before** the temperature drop, i.e. does it "see" the front coming? Do hidden states and gate activations separate event from normal hours (UMAP / k-NN coloured by event)? Which input patches and which **stations** matter for a correct event forecast (saliency over time and over inputs)? |

**Note on TiRex-2:** the model takes multivariate input with past covariates,
so step (c) is a supported use of the model. How many extra series fit into
one forecast in practice (memory, speed) is something to check early.

## Dataset

Our own dataset, built from **GeoSphere Austria open data** (CC BY 4.0). It
covers **one year of hourly data, 2025-10-01 → 2026-10-01 (8,760 hours)**.
Everything about it is documented in
[`data_acquisition/README.md`](data_acquisition/README.md): source, API,
method, caveats, and how to download or rebuild it.

| | **Austria 5 km** (main) | Tyrol 1 km |
|---|---|---|
| Area | All of Austria (~570 km west–east) | Innsbruck – Wipp valley – Brenner |
| Locations | 3,363 lattice points | 3,306 grid cells |
| Rows (location × hour) | 29.5 M | 29.0 M |
| Variables | `T2M`, humidity, dew point, wind (u/v), sea-level pressure, radiation, precipitation | same |
| Role | Cold waves and thunderstorms moving **across the country**; choose upstream/downstream locations | Small-scale, dense detail (e.g. valley vs. mountain) |

Why this data rather than a standard benchmark (GIFT-Eval / fev-bench):
- **Space and time together.** A standard benchmark has independent series.
  Ours are neighbouring locations, so we can test whether upstream information
  helps.
- **Real events.** Thunderstorms and cold waves are real, abrupt changes in
  the series, not synthetic change points.
- **Large enough to be systematic:** thousands of series, about 10
  thunderstorm events per location, and 29 country-wide cold-wave days.
- **Local and checkable.** We know the region and can check events against
  weather reports.

GIFT-Eval's weather subset remains an option as a **sanity reference**, to
check that TiRex-2 behaves as published on standard data before we interpret
anything on ours.

**Known limitations:**
- The variables are INCA analyses, which are model-assisted, not raw
  measurements. Very local thunderstorms may be smoothed out.
- **No lightning data.** "Thunderstorm" means a temperature drop plus heavy
  rain. Lightning data would be better but isn't in the open dataset.
- The event thresholds are a first draft. Several of the large cold-wave days
  fall in summer, so some may be thunderstorm outflows rather than classic
  cold fronts. We should tune the definitions together.
- One year means each season occurs only once.
- The foehn labels from the first data version stay in the data. They're no
  longer the focus, but useful as extra context: foehn often ends with a cold
  front.

## Decision

Fill in once all four agree. The proposals are pre-filled.

- **Final task framing:** *proposal:* forecast temperature change (ΔT) with
  TiRex-2 zero-shot, measure the gain from (b) local covariates and (c) other
  / upstream stations, evaluate on thunderstorm and cold-wave events.
  → ☐ agreed
- **Target and horizon:** *proposal:* `T2M`, analysed as ΔT; horizon 6–24 h.
  → ☐ agreed
- **Event definitions:** *proposal:* the two proxies above as a starting
  point, finalised in the first week of Phase I. → ☐ agreed
- **Final dataset(s):** *proposal:* **Austria 5 km** as the main dataset,
  Tyrol 1 km for detail. → ☐ agreed
- **Scope:** *proposal:* single-model deep dive on TiRex-2, with GIFT-Eval
  weather as a sanity check only. → ☐ agreed
- **Registered on the course form:** ☐ (who, date)
