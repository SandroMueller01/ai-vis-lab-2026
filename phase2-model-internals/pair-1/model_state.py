"""The model state used in Phase II questions D and E (Pair 1).

State = output of the last block of TiRex-2 at the last context patch, i.e. the token that holds the newest observed
hours. Both notebooks import it from here, so D and E use exactly the same state.

Token layout (tirex-2 0.3.1, ``TiRex2._fix_context_size``): the input is padded with NaN on the left to ``context_len``
and on the right by ``future_len``, then cut into patches of ``input_patch_size``. With ``L`` tokens, the last
``future_len / input_patch_size`` tokens are the forecast window, so the last context token is
``L - future_len // input_patch_size - 1``.
"""

from __future__ import annotations

import numpy as np
import torch
from tirex2 import TimeseriesType


def _as_series(contexts) -> list[TimeseriesType]:
    if isinstance(contexts, np.ndarray):
        contexts = [torch.from_numpy(np.asarray(c, np.float32)[None].copy()) for c in contexts]
    return [c if isinstance(c, TimeseriesType) else TimeseriesType(c, None, None) for c in contexts]


def context_token(core, n_tokens: int) -> int:
    """Index of the last context token for a sequence of ``n_tokens`` tokens."""
    return n_tokens - core.future_len // core.input_patch_size - 1


def hidden_states(model, contexts, horizon: int = 24):
    """Output of every block for univariate contexts, first (unflipped) pass: [blocks, series, tokens, dim]."""
    core = model.model
    out = []
    hooks = [b.register_forward_hook(lambda m, a, o: out.append(o[0].detach().cpu())) for b in core.stack]
    try:
        with torch.no_grad():
            core._predict(_as_series(contexts), horizon, tta_diff=core.tta_diff)
    finally:
        for h in hooks:
            h.remove()
    return torch.stack(out[: len(core.stack)]).numpy()


def state_and_forecast(model, contexts, horizon: int = 24, batch_size: int = 128):
    """State (last block, last context token) and the normal forecast of each context.

    contexts: array [n, T] (NaN allowed) or a list of univariate TimeseriesType.
    Returns states [n, dim] float32 and forecasts [n, 9, horizon] float32; the forecast is the same as
    ``model.forecast(...)`` (both TTA passes), the state is taken from the first, unflipped pass.
    """
    core = model.model
    series = _as_series(contexts)
    states, preds = [], []
    for s in range(0, len(series), batch_size):
        chunk = series[s : s + batch_size]
        out = []
        hook = core.stack[-1].register_forward_hook(lambda m, a, o, out=out: out.append(o[0].detach()))
        try:
            pred = core.predict(chunk, horizon)
        finally:
            hook.remove()
        h = out[0]  # first pass; one row per series (univariate, one group each)
        assert h.shape[0] == len(chunk), "state function expects univariate contexts"
        states.append(h[:, context_token(core, h.shape[1])].float().cpu().numpy())
        preds.append(torch.stack([p[0] for p in pred]).float().cpu().numpy())
    return np.concatenate(states), np.concatenate(preds)
