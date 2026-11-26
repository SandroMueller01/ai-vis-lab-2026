"""Minimal eager-PyTorch examples for TiRex-2 internal visualizations.

Source inspected/tested: NX-AI/tirex-2 at
9e9d19a1767845e986a084924ddb64eb1aa1c49a (version string 0.5.0).
Checkpoint: NX-AI/TiRex-2 at 30788a311699acba7e6393ad9700ea7b7cb9bb2d.
These are research helpers using private APIs, not official explanation APIs.
The sLSTM pointwise instrumentation follows the Apache-2.0 NXAI implementation:
https://github.com/NX-AI/tirex-2/blob/9e9d19a1767845e986a084924ddb64eb1aa1c49a/src/tirex2/model/component/kernel/slstm_torch.py
Copyright (c) NXAI GmbH; https://www.apache.org/licenses/LICENSE-2.0

Install PyTorch >=2.8 for your platform, then:
    pip install 'tirex-2 @ git+https://github.com/NX-AI/tirex-2.git@9e9d19a1767845e986a084924ddb64eb1aa1c49a' matplotlib
Run:
    python tirex2_internal_maps.py
    python tirex2_internal_maps.py --checkpoint /path/to/local/checkpoint

Default demo: one synthetic hourly target, 512 context points, 24-hour horizon.
Use CPU and eager execution first. All functions can be imported into a notebook.
"""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import argparse
import importlib

import torch
import torch.nn.functional as F
from tirex2 import TimeseriesType, load_model

CHECKPOINT_REVISION = "30788a311699acba7e6393ad9700ea7b7cb9bb2d"


def finite_scale(scaler, x):
    """NaN-masked equivalent of Scaler.scale, with finite input gradients.

    Stock scaling squares NaNs before nanmean; its input backward can produce
    NaNs even at observed positions. Mask BEFORE arithmetic. Keep missingness,
    binary handling, arcsinh and the return-state format. No imputation is fed
    to the model. Compare forward values with stock forecasts on your data.
    """
    valid = ~torch.isnan(x)
    clean = torch.where(valid, x, 0.0)
    count = valid.sum(-1, keepdim=True)
    loc = clean.sum(-1, keepdim=True) / count.clamp_min(1)
    centered = torch.where(valid, clean - loc, 0.0)
    variance = centered.square().sum(-1, keepdim=True) / count.clamp_min(1)
    variance = torch.where(count > 0, variance, torch.ones_like(variance))
    scale = variance.clamp_min(scaler.eps ** 2).sqrt()
    binary = ((clean == 0) | (clean == 1) | ~valid).all(-1, keepdim=True) if scaler.binaryaware else None
    if binary is not None:
        loc = torch.where(binary, 0.0, loc)
        scale = torch.where(binary, 1.0, scale)
    normalized = (clean - loc) / scale
    if scaler.use_arcsinh:
        squashed = normalized.asinh()
        normalized = torch.where(binary, normalized, squashed) if binary is not None else squashed
    normalized = torch.where(valid, normalized, torch.full_like(normalized, torch.nan))
    return normalized, (loc, scale, binary)


def differentiable_forecast(model, target, prediction_length=24, *,
                            past_covariates=None, future_covariates=None,
                            tta_diff=None, pad_context=True):
    """One pass in level units; corresponds to public tta_sign_flip=False.

    model is load_model(...).model. Input tensors should be CPU float32 leaves
    with requires_grad=True when you want their saliency. tta_diff=None follows
    the checkpoint default. Its discrete trend decision is held on its chosen
    branch during differentiation. Do not wrap this call in inference_mode.
    """
    ts = TimeseriesType(target, past_covariates, future_covariates)
    diff = model.tta_diff if tta_diff is None else tta_diff
    with torch.enable_grad(), patch.object(model.scaler, "scale", lambda x: finite_scale(model.scaler, x)):
        return model._predict([ts], prediction_length=prediction_length,
                              preserve_grad=True, tta_diff=diff,
                              pad_context=pad_context)[0]  # [V_target, Q, H]


def input_saliency(forecast, inputs, q_index, horizons=None):
    """Signed horizon-by-variate-by-hour Jacobian for a chosen output target 0.

    inputs may instead be a past/future covariate leaf to explain that input.
    No per-row normalization is applied; retain the magnitudes for comparisons.
    """
    horizons = range(forecast.shape[-1]) if horizons is None else horizons
    return torch.stack([torch.autograd.grad(forecast[0, q_index, h], inputs,
                                            retain_graph=True)[0]
                        for h in horizons]).detach()


@contextmanager
def trace_slstm(cell):
    """Expose actual stabilized sLSTM gates and states for one selected cell.

    Temporary instrumentation of the torch pointwise kernel. Restored on exit.
    calls[0] is forward; if known future covariates exist, calls[1] is reverse
    over those covariates, in reversed token order. Do not run forecasts from
    other threads during this context (the pointwise patch is module-global).
    """
    if cell.config.backend != "torch":
        raise ValueError("Load on CPU for this example; the torch sLSTM backend is required.")
    kernel = importlib.import_module("tirex2.model.component.kernel.slstm_torch")
    original_recurrence = cell.recurrence
    calls = []

    def recurrence(*args, **kwargs):
        steps = []

        def pointwise(Wx, Ry, b, states):
            # Preserve the implementation's stabilization, clamps and gate order.
            input_logit, forget_logit, candidate_logit, output_logit = (Wx + Ry + b).unbind(-2)
            _, previous_c, previous_n, previous_m = states
            log_retained = previous_m + F.logsigmoid(forget_logit.clamp(max=15))
            new_m = torch.where(previous_n == 0, input_logit,
                                torch.maximum(input_logit, log_retained))
            gates = {
                "i": (input_logit - new_m).exp().clamp(max=1),
                "f": (log_retained - new_m).exp().clamp(max=1),
                "z": candidate_logit.tanh(),
                "o": output_logit.sigmoid(),
            }
            new_c = gates["f"] * previous_c + gates["i"] * gates["z"]
            new_n = (gates["f"] * previous_n + gates["i"]).clamp(min=1)
            new_y = gates["o"] * new_c / new_n
            steps.append({**gates, "c": new_c, "n": new_n, "m": new_m, "y": new_y})
            return [new_y, new_c, new_n, new_m]

        with patch.object(kernel, "slstm_torch_pointwise", pointwise):
            output = original_recurrence(*args, **kwargs)
        calls.append(steps)
        return output

    with patch.object(cell, "recurrence", recurrence):
        yield calls


def gate_saliency(score, steps, row=0):
    """Mean |gate * d(score)/d(gate)| over heads/channels: [4, tokens].

    Rows: i, f, z, o. A local zero-reference gate sensitivity, not a complete
    attribution decomposition. Actual gates, not just their input projections.
    """
    nodes = [step[name] for name in ("i", "f", "z", "o") for step in steps]
    gradients = torch.autograd.grad(score, nodes, allow_unused=True, retain_graph=True)
    scores = [torch.zeros((), device=g.device) if grad is None else
              (g[row] * grad[row]).abs().mean() for g, grad in zip(nodes, gradients)]
    return torch.stack(scores).reshape(4, len(steps)).detach()


@torch.no_grad()
def memory_flow(steps, row=0):
    """Realized per-source contributions to pre-normalization sLSTM y_t.

    Zero initial memory. R[t,j,d] = i[j,d] * product(f[j+1:t+1,d]).
    y[t,d] = sum_j o[t,d]/n[t,d] * R[t,j,d] * z[j,d].
    Returns mean absolute source contribution [receiver token, source token],
    and signed reconstructed hidden states [tokens, heads, channels] for QA.
    This holds realized gates fixed; it omits indirect recurrent feedback.
    """
    candidate = torch.stack([s["z"][row] for s in steps], dim=-1)
    transport = torch.zeros_like(candidate)
    flow, reconstructed = [], []
    for t, step in enumerate(steps):
        transport = transport * step["f"][row, ..., None]
        transport[..., t] += step["i"][row]
        terms = transport * candidate * (step["o"][row] / step["n"][row])[..., None]
        flow.append(terms.abs().mean(dim=(0, 1)))
        reconstructed.append(terms.sum(-1))
    return torch.stack(flow), torch.stack(reconstructed)


@contextmanager
def trace_mlstm(cell):
    """Capture the q/k/v and capped gate logits actually passed to mLSTM."""
    calls = []
    original = cell.mlstm_kernel

    def kernel(**kwargs):
        output = original(**kwargs)
        calls.append({**{k: v.detach() for k, v in kwargs.items()}, "h": output.detach()})
        return output

    with patch.object(cell, "mlstm_kernel", kernel):
        yield calls


@torch.no_grad()
def temporal_coefficients(call):
    """Signed mLSTM value-mixing coefficients [rows, heads, receiver, source].

    Reconstructs the zero-state native kernel before multihead normalization,
    output gating, output projection, residuals and other layers. Not softmax.
    Use abs(A) / abs(A).sum(-1) only as a separate display normalization.
    """
    q, k, i, f = (call[name].float() for name in ("q", "k", "i", "f"))
    prefix = F.logsigmoid(f).cumsum(-1)
    log_weight = i.unsqueeze(-2) + prefix.unsqueeze(-1) - prefix.unsqueeze(-2)
    causal = torch.ones(log_weight.shape[-2:], dtype=torch.bool, device=q.device).tril()
    log_weight = log_weight.masked_fill(~causal, -torch.inf)
    # Include the zero-state stabilizer propagated from initial m=0.
    stabilizer = torch.maximum(prefix, log_weight.max(-1).values)
    decay = (log_weight - stabilizer.unsqueeze(-1)).exp()
    numerator = (q @ k.transpose(-1, -2)) * (q.shape[-1] ** -0.5) * decay
    denominator = torch.maximum(numerator.sum(-1).abs(), (-stabilizer).exp()) + 1e-6
    return numerator / denominator.unsqueeze(-1)


def plot_heatmap(values, filename, title, xlabel, ylabel, *, signed=False,
                 extent=None, yticks=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    array = values.detach().cpu().numpy()
    fig, ax = plt.subplots(figsize=(10, 4))
    limit = max(float(abs(array).max()), 1e-12)
    im = ax.imshow(array, aspect="auto", origin="lower", interpolation="nearest",
                   cmap="RdBu_r" if signed else "magma", extent=extent,
                   vmin=-limit if signed else 0, vmax=limit)
    if yticks is not None:
        ax.set_yticks(range(len(yticks)), yticks)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    fig.colorbar(im, ax=ax, label="Signed coefficient / sensitivity" if signed else "Magnitude")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="NX-AI/TiRex-2")
    parser.add_argument("--out", default="tirex2_maps")
    parser.add_argument("--context", type=int, default=512)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--slstm-layer", type=int, default=1)
    parser.add_argument("--mlstm-layer", type=int, default=0)
    args = parser.parse_args()
    if args.context < 2 or args.horizon < 1:
        parser.error("context must be >=2 and horizon must be >=1")
    torch.set_num_threads(2)
    torch.manual_seed(0)
    model = load_model(args.checkpoint, device="cpu", compile=False, cuda_graphs=False,
                       hf_kwargs={"revision": CHECKPOINT_REVISION}).model
    model.eval().requires_grad_(False)
    if args.horizon > model.future_len:
        parser.error(f"horizon must be <= {model.future_len} for this checkpoint")
    slstm = model.stack[args.slstm_layer].time_mixer.fwd_cell
    mlstm = model.stack[args.mlstm_layer].time_mixer.fwd_cell
    if not hasattr(slstm, "recurrence") or not hasattr(mlstm, "mlstm_kernel"):
        raise ValueError("Select an sLSTM layer and an mLSTM layer, respectively.")
    # Replace this with your observed target, shape [num_targets, context_hours].
    t = torch.arange(args.context, dtype=torch.float32)
    target = (10 + 3 * torch.sin(2 * torch.pi * t / 24)
              - 5 * torch.sigmoid((t - args.context + 30) / 3)).view(1, -1).requires_grad_()
    q = int((model.quantiles - 0.5).abs().argmin())
    ts = TimeseriesType(target.detach(), None, None)
    with torch.no_grad():
        stock = model.predict([ts], args.horizon, tta_sign_flip=False)[0]
    with trace_slstm(slstm) as slstm_calls, trace_mlstm(mlstm) as mlstm_calls:
        forecast = differentiable_forecast(model, target, args.horizon)
    torch.testing.assert_close(forecast.detach(), stock, rtol=3e-4, atol=3e-4)
    steps = slstm_calls[0]  # target 0 in the forward call
    score = forecast[0, q, -1]  # median temperature at the last requested lead
    gates = gate_saliency(score, steps)
    horizons = sorted(set([0, min(11, args.horizon - 1), args.horizon - 1]))
    jacobian = input_saliency(forecast, target, q, horizons)
    if not torch.isfinite(jacobian).all():
        raise RuntimeError("Input gradients are nonfinite; inspect preprocessing before plotting.")
    flow, reconstructed = memory_flow(steps)
    hidden = torch.stack([step["y"][0].detach() for step in steps])
    torch.testing.assert_close(reconstructed, hidden, rtol=3e-4, atol=3e-4)
    coefficients = temporal_coefficients(mlstm_calls[0])
    torch.testing.assert_close(coefficients @ mlstm_calls[0]["v"], mlstm_calls[0]["h"],
                               rtol=3e-3, atol=3e-3)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # Token spans include actual missing/padding tokens processed by the model.
    token_count = len(steps)
    patch_size = model.input_patch_size
    left = token_count * patch_size - model.future_len - target.shape[-1]
    token_start_hours = torch.arange(token_count) * patch_size - left - target.shape[-1]
    # Each input token predicts the NEXT patch. Hours 1..32 use the last
    # context token; the last processed token predicts beyond the forecast.
    receiver = token_count - model.future_len // patch_size - 1 + (args.horizon - 1) // patch_size
    plot_heatmap(jacobian[:, 0], out / "input_saliency.png", "Input saliency: median temperature",
                 "Input hour index (oldest to newest)", "Forecast lead (hours)",
                 signed=True, yticks=[str(h + 1) for h in horizons])
    plot_heatmap(gates, out / "gate_saliency.png", f"sLSTM layer {args.slstm_layer}: gate saliency",
                 "Processed token index (includes padding and future placeholders)", "Gate",
                 yticks=["input i", "forget f", "candidate z", "output o"])
    plot_heatmap(flow, out / "memory_flow.png", f"sLSTM layer {args.slstm_layer}: realized memory transport",
                 "Source token", "Receiver token")
    # Show one head to preserve signs; averaging heads can cancel different paths.
    plot_heatmap(coefficients[0, 0], out / "temporal_coefficients.png",
                 f"mLSTM layer {args.mlstm_layer}, head 0: signed temporal coefficients",
                 "Source token", "Receiver token", signed=True)
    import numpy as np
    np.savez(out / "maps.npz", forecast=forecast.detach().numpy(),
             input_saliency=jacobian.numpy(), horizons=[h + 1 for h in horizons],
             gate_saliency=gates.numpy(), memory_flow=flow.numpy(),
             temporal_coefficients=coefficients.numpy(), token_start_hours=token_start_hours.numpy(),
             score_receiver_token=receiver)
    print(f"Patch width/stride: {patch_size}/{model.tokenizer.input_patch_stride} samples")
    print(f"Last-lead output reads receiver token {receiver}; its input patch starts at hour {int(token_start_hours[receiver])}.")
    print(f"Finite gradients; stock forecast, sLSTM transport and mLSTM reconstruction checks passed.")
    print(f"Saved four PNGs and maps.npz in {out.resolve()}")


if __name__ == "__main__":
    main()
