# TiRex-2: saliency, gates, memory flow and temporal mixing

Checked on 12 November 2026 against the official `NX-AI/tirex-2` source at commit `9e9d19a1767845e986a084924ddb64eb1aa1c49a` (package version metadata: `0.5.0`) and checkpoint `NX-AI/TiRex-2` at revision `30788a311699acba7e6393ad9700ea7b7cb9bb2d`.

The accompanying `tirex2_internal_maps.py` is an executable, pure Python example. It uses the official weights and PyTorch implementation. It adds temporary research instrumentation; the explanation helpers are not official package APIs. The exact source commit is pinned because private method names and kernel implementations can change even when package version metadata stays the same.

## What you can obtain

| View | Computation | Access point | Axes | Interpretation |
|---|---|---|---|---|
| Input saliency | Signed derivative of one forecast quantile at each chosen lead with respect to raw input values | Undecorated `TiRex2._predict(..., preserve_grad=True)` | Forecast lead × observed input hour, separately per input variate | Local sensitivity of the final, postprocessed forecast |
| Gate saliency | Mean absolute `gate * derivative(score, gate)` | Instrument the sLSTM PyTorch pointwise recurrence | Gate × processed token, optionally keep heads/channels | Local sensitivity to actual stabilized input, forget, candidate and output gates |
| Memory flow | Track realized write coefficients through successive forget gates and the cell readout | The same sLSTM trace | Receiving token × write token | A decomposition of the cell's realized hidden state with gates held at their observed values |
| Attention-like temporal map | Reconstruct mLSTM's gated query/key value-mixing coefficients | Wrap `mLSTMLayer.mlstm_kernel` to capture its actual arguments | Receiving token × source token, per layer/head/variate | Signed, causal temporal mixing inside one mLSTM cell |

The default checkpoint alternates mLSTM and sLSTM blocks: zero-based layer 0 is mLSTM, layer 1 is sLSTM, and so on. Every block also has an attention-based variate mixer. That attention is **between variables at the same token position**, rather than a temporal attention matrix. In the current implementation it is skipped for groups containing only one variable.

## Install and run

Install PyTorch >=2.8 for your platform, then install the inspected official source revision and the plotting dependency:

```bash
python -m pip install "tirex-2 @ git+https://github.com/NX-AI/tirex-2.git@9e9d19a1767845e986a084924ddb64eb1aa1c49a" matplotlib
python tirex2_internal_maps.py
```

Or reuse an existing local checkpoint directory containing `config.json` and `model.safetensors`:

```bash
python tirex2_internal_maps.py --checkpoint /path/to/checkpoint --out maps
```

The demo uses a synthetic hourly target with a daily cycle and a recent temperature decline. It writes four PNGs and an NPZ containing the numeric maps. These synthetic examples are for checking instrumentation, not evidence about Austrian weather forecasts.

Start with CPU, `compile=False`, `cuda_graphs=False`, and a single forecasting example. This makes the Python sLSTM recurrence visible and avoids fused inference-only execution paths. `eval()` disables training behavior such as dropout; it does not itself disable gradients. Freeze model parameters to save memory, while making the input tensors require gradients.

## 1. Input saliency

For input variate v, observed time t, output target r, quantile q and lead h, use:

\[
J_{h,v,t}=\frac{\partial\widehat y_{r,q,h}}{\partial x_{v,t}}.
\]

A signed heatmap answers whether a small increase in an observed value locally raises or lowers the chosen forecast. An absolute heatmap shows sensitivity magnitude. Keep signed values in the saved arrays even if you display magnitudes.

```python
import torch
from tirex2 import load_model
from tirex2_internal_maps import differentiable_forecast, input_saliency

model = load_model("NX-AI/TiRex-2", device="cpu",
                   compile=False, cuda_graphs=False).model
model.eval().requires_grad_(False)

# Replace this with observed temperature, [number of target variates, hours].
t = torch.arange(512, dtype=torch.float32)
x = (10 + 3 * torch.sin(2 * torch.pi * t / 24)).view(1, -1)
x = x.clone().detach().requires_grad_(True)

prediction = differentiable_forecast(model, x, prediction_length=24)
q50 = int((model.quantiles - 0.5).abs().argmin())
J = input_saliency(prediction, x, q50)  # [24 leads, 1 target variate, 512 hours]
```

The usual public `model.forecast(...)` eventually calls a `predict` method decorated with `torch.no_grad`. Calling it inside `torch.enable_grad()` does not remove that inner decorator. Merely passing `preserve_grad=True` to the public method is therefore insufficient. The helper calls the underlying `_predict` method directly and preserves output postprocessing gradients.

There is a second obstacle: stock scaling can yield NaN gradients to raw inputs, because NaN padding participates in arithmetic before the variance reduction masks it. I reproduced this with the inspected source. The helper temporarily uses `finite_scale`, which masks missing entries **before** arithmetic, preserves their missingness in the returned tensor, and preserves the scaler's arcsinh and binary-variable behavior. It is not zero-imputing missing observations into the model. The demo checks forecast parity with the stock implementation. Always inspect `torch.isfinite(J)`; replacing NaN gradients with zero would conceal the problem.

These derivatives include normalization and output postprocessing, so they describe the deployed forecast on its chosen preprocessing branch. With `tta_diff=None`, the helper follows the checkpoint's differencing setting. The threshold-based decision to difference a trending series is discrete: gradients do not explain crossing that threshold. The single-pass helper corresponds to `tta_sign_flip=False`; if Phase I enabled sign-flip augmentation, combine differentiable predictions for x and -x using the same quantile-complement mapping before computing gradients.

For a more stable input attribution, integrated gradients or noise-averaged gradients can reuse the same differentiable wrapper. Choose weather-appropriate baselines and perturbations. Constant and binary baselines can trigger different scaler branches; integrated gradients also need care when the trend-detection branch changes along the path. A finite-difference or perturbation comparison is useful, with several perturbation sizes: sLSTM rounds recurrent operands to BF16, so tiny finite differences need not agree closely with autograd through those casts.

## 2. Gate saliency

Gate activation and gate saliency answer different questions. A large forget gate indicates retention in the realized recurrence; it does not show that the retained information matters for your selected forecast. Choose an output score S and differentiate it with respect to the gates used by the recurrence:

\[
G_{g,t}=\operatorname{mean}_{heads,channels}
\left|g_t\frac{\partial S}{\partial g_t}\right|.
\]

```python
from tirex2_internal_maps import trace_slstm, gate_saliency

cell = model.stack[1].time_mixer.fwd_cell
with trace_slstm(cell) as calls:
    prediction = differentiable_forecast(model, x, prediction_length=24)

steps = calls[0]  # Forward call; row 0 is the first target in this example.
score = prediction[0, q50, 23]  # Temperature at lead +24 hours.
G = gate_saliency(score, steps)  # [4 gates, number of processed tokens]
```

Rows of G are input i, forget f, candidate z and output o. The trace records the **actual stabilized gate activations** involved in computing the states, keeping their computation graph. Hooking only `gate_proj` would instead expose input-derived gate preactivations; sLSTM adds recurrent contributions and applies normalization/stabilization afterward. The trace follows the executed kernel's gate order rather than inferring it from projection comments.

`gate * gradient` is a zero-reference local score, not a complete additive attribution of the forecast. In particular, the two stabilized exponential gates are coupled through the stabilizer. Compare activation maps and sensitivity maps; examine individual heads/channels before aggregating. `steps[t]["c"]`, `["n"]`, `["m"]`, and `["y"]` provide the memory, normalizer, stabilizer and hidden state for state heatmaps as well.

The instrumentation temporarily replaces the Python pointwise function while the selected cell runs and restores it afterward. Do not run unrelated forecasts concurrently in other threads during this context. With future-known covariates, the shared cell runs a second time in reverse: `calls[1]` contains only those covariates, in reversed token order. Map both its row identities and time order back before comparing it with the forward trace.

## 3. Memory-flow visualization

For one channel, the executed sLSTM update has the form:

\[
c_t=f_t c_{t-1}+i_t z_t,\qquad
y_t=o_t c_t/n_t.
\]

The actual n includes the kernel's normalization/clamping. Starting from zero memory, freeze the realized gates and expand:

\[
R_{t,j}=i_j\prod_{k=j+1}^{t} f_k,\qquad
y_t=\sum_{j\le t}\frac{o_t}{n_t}R_{t,j}z_j.
\]

```python
from tirex2_internal_maps import memory_flow

flow, reconstructed_y = memory_flow(steps)
# flow: [receiver token, write token]
# Each entry averages the absolute per-channel contribution to y_t.
```

This produces a lower-triangular map: a source column extending across many later receiver rows indicates a persistent write. The demo checks that the signed contributions reconstruct the recorded hidden states before group normalization. You can also plot `i*z` versus `f*c_previous`, or channel-specific c/n trajectories around a front passage.

Treat the source axis as **write time**, not as attribution to one original weather observation. Gates and candidates already depend on earlier hidden states; fixing their realized values omits the indirect route by which an earlier observation changes later gates. The map also excludes layer residuals, feed-forward computation, variate mixing and later layers. Use final-output saliency or interventions to test whether an apparent transport path matters for a forecast.

## 4. Attention-like temporal maps

mLSTM is particularly suitable for this view because its matrix memory admits a temporal value-mixing representation. The helper captures the actual q, k, v and soft-capped input/forget logits passed into the native kernel:

```python
from tirex2_internal_maps import trace_mlstm, temporal_coefficients

cell = model.stack[0].time_mixer.fwd_cell
with trace_mlstm(cell) as calls_m:
    prediction = differentiable_forecast(model, x, prediction_length=24)

A = temporal_coefficients(calls_m[0])
# [forward rows, heads, receiver token, source token]
one_head = A[0, 0]

# Optional display-only relative magnitude. Retain signed A as well.
relative = one_head.abs() / one_head.abs().sum(-1, keepdim=True).clamp_min(1e-12)
```

Ignoring numerical stabilization for notation, the pre-normalization coefficient is proportional to:

\[
(q_t^\top k_j)/\sqrt{d_k}\;\exp(i_j)
\prod_{k=j+1}^{t}\sigma(f_k),\qquad j\le t.
\]

The implementation also reconstructs the native stabilizer and denominator. It checks that `A @ v` matches the kernel output before multihead normalization, output gating and projection.

Unlike softmax attention, the coefficients can be negative and need not sum to one. Absolute row normalization is a visualization choice, not a model probability. A later-layer map operates on contextualized representations, rather than directly on original measurements. The horizon-by-input Jacobian from section 1 is another useful attention-shaped temporal map, with a more direct connection to the selected final forecast.

## Covariates and alternative scores

Make each input group a separate leaf, keeping its real shape:

```python
past = observed_covariates.clone().detach().float().requires_grad_(True)
# past shape: [number of covariates, context hours]
prediction = differentiable_forecast(model, x, 24, past_covariates=past)
J_past = input_saliency(prediction, past, q50)
```

Future-known covariates have shape `[number of covariates, context_hours + prediction_length]`. Only put genuinely available future information there. To compare temperature, pressure and wind sensitivities, account for their different units, for example by multiplying derivatives by a prespecified meaningful perturbation scale. The helper currently explains output target 0; change `forecast[0, ...]` in `input_saliency` or choose a scalar score yourself for another target.

Possible scalar scores include:

```python
S_temperature = prediction[0, q50, 23]
S_forecast_swing = prediction[0, q50, 23] - prediction[0, q50, 0]
S_change_from_now = prediction[0, q50, 23] - x[0, -1]
q10 = int((model.quantiles - 0.1).abs().argmin())
q90 = int((model.quantiles - 0.9).abs().argmin())
S_width = prediction[0, q90, 23] - prediction[0, q10, 23]
```

The gradient of `S_change_from_now` includes the explicit subtraction of the last observation. Width sensitivity explains changes in reported intervals; it does not establish probabilistic calibration. Quantile sorting and trend detection make the forecast piecewise differentiable.

## Temporal alignment and the Phase I hypotheses

The default checkpoint has patch width **32** and stride **32** samples. With hourly data, internal gate and memory maps therefore have 32-hour token resolution, while raw-input saliency still has hourly resolution through the patch embedding. Repeating each internal score 32 times for display would not add within-patch information.

Keep the same `pad_context`, differencing and augmentation settings as Phase I. The default `pad_context=True` pads short histories to the 2,048-hour context. The model also processes missing future placeholders up to its internal 320-hour future window, even when requesting only 24 hours. Padding tokens can affect recurrent states; omit them only from displays when appropriate, not from the instrumented computation.

Each processed token predicts the **next** output patch. For the default 74-token padded input, forecast hours +1 through +32 are emitted from receiver token 63, whose input patch covers hours -32 through -1. The final processed token predicts beyond the retained forecast. The demo stores `token_start_hours` and `score_receiver_token` to make this shift explicit. For differenced targets, later level forecasts integrate earlier predicted increments, so several receiver tokens can contribute to a long-lead score. Later-layer temporal mixing also combines paths from earlier blocks.

For your Phase II analysis, useful comparisons are:

1. **The 32-hour history pattern:** compare hourly saliency by within-patch position (lag modulo 32), split by lead and season. Test shifted history windows or front onsets with suitable controls, since a shift also changes the available history. The patch size is a concrete candidate mechanism, not proof that it caused the Phase I result.
2. **Damped cooling and warming:** compare front/strong-change cases with matched stable cases, using lead-specific scores, gate sensitivity and recent-write retention. Match season, location and input scale. Keep comparable color scales and report both raw sensitivity and the fraction concentrated in recent history.
3. **Cold-state retention after passage:** align traces to the observed transition and compare before/after cases. Look for persistent cold-related writes, then perturb or ablate those paths to test their effect on the forecast.
4. **Intervals missing fronts:** explain median and interval-width scores separately. Compare their input and gate sensitivities across well-covered and missed events, while holding lead time fixed.

Use weather events or nonoverlapping temporal blocks as resampling units where possible: overlapping forecast starts and neighboring stations are dependent. Outcome-defined strong-change groups are retrospective explanatory cohorts, not information available at forecast time. These maps suggest mechanisms; controlled interventions are needed for causal claims.

## Validation performed

The example was run with the real pretrained checkpoint on CPU using PyTorch 2.9.1. Validation checked finite input gradients, agreement of instrumented and stock forecast values, reconstruction of sLSTM hidden states from transported writes, and reconstruction of the mLSTM kernel output from temporal coefficients. A separate multivariate check exercised past-only and future-known covariates, forward/reverse cell calls, a non-patch-aligned context length, and both enabled/disabled differencing. These checks validate the instrumentation on those examples; they do not establish explanation faithfulness on the weather dataset. GPU execution was not tested.

## Official source references

- [Forecasting API and execution options](https://nx-ai.github.io/tirex-2/how-to/forecasting/)
- [Backbone, public `predict`, private `_predict`, preprocessing and output alignment](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/tirex2.py)
- [sLSTM layer and recurrent layouts](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/slstm_block.py)
- [Executed sLSTM pointwise equations](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/kernel/slstm_torch.py)
- [mLSTM projections and gate soft caps](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/mlstm_block.py)
- [Native mLSTM kernel and stabilizer](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/kernel/mlstm_native.py)
- [Time/variate mixing axes](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/variate_mixing_block.py)
- [Scaler](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/scaler.py)
- [Postprocessor and differentiable output path](https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/postprocessor.py)
- [Checkpoint configuration](https://huggingface.co/NX-AI/TiRex-2/blob/30788a311699acba7e6393ad9700ea7b7cb9bb2d/config.json)
