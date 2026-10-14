# Model Selection

Due: **28.10.2026, 23:59** — register the final choice via the course's
model-selection form once the group has agreed.

## Model

**TiRex-2** (NX-AI / JKU) — recurrent xLSTM-based zero-shot time-series
forecasting foundation model, single checkpoint for univariate and
multivariate forecasting with optional past/future covariates, streaming-
capable at constant per-patch cost.

- Paper: [arXiv:2607.01204](https://arxiv.org/abs/2607.01204)
- Code: [github.com/NX-AI/tirex-2](https://github.com/NX-AI/tirex-2)
- Weights: [huggingface.co/NX-AI/TiRex-2](https://huggingface.co/NX-AI/TiRex-2)
- Discriminative/generative: forecasting (regression-style, quantile output),
  not a classifier or text generator — the "task" framing below should make
  this concrete.

## Task — to be finalized by the full group

The assignment wants a specific task, not "forecasting in general." Candidate
framings (pick one, or narrow further):

1. **Zero-shot univariate forecasting** on a fixed benchmark subset (e.g. a
   handful of GIFT-Eval domains: energy, traffic, finance, weather) — compare
   behavior *across domains* rather than just reporting an aggregate score.
2. **Multivariate vs. univariate gap**: same series, forecast with and
   without covariates, characterize where/why covariates help or hurt.
3. **Streaming robustness**: forecast quality and representation stability as
   context length grows via streaming updates, vs. a single long-context
   call.
4. **Regime-shift / distribution-shift sensitivity**: synthetic or real series
   with an injected change point, characterize how forecasts and internals
   react before/after.

Options 2–4 give Phase II a more specific, pre-baked hypothesis to open the
black box around; option 1 is the safer default if the group wants to decide
the specific angle after seeing Phase I results.

## Input dataset / benchmark

- **[GIFT-Eval](https://huggingface.co/spaces/Salesforce/GIFT-Eval)** and/or
  **[fev-bench](https://github.com/autogluon/fev)** — the two established
  benchmarks TiRex-2 itself is evaluated against, so there's a known-good
  data loading path and published reference numbers to compare behavior
  against.
- Supplement with a **synthetic set** for whichever specific hypothesis the
  group picks in the task framing above (e.g. injected regime shifts,
  missing/corrupted covariates, pathological context lengths) — the
  assignment explicitly allows this and it's often the fastest way to isolate
  one mechanism cleanly.
- Needs to be large enough that any reported pattern is systematic behavior,
  not a handful of cherry-picked series.

## Decision

All four group members decide this together — the above is a starting menu,
not a final answer. Fill in once agreed:

- Final task framing: TBD
- Final dataset(s): TBD
- Scope: single-model deep dive (current plan) vs. comparing TiRex-2 against
  a second model: TBD
