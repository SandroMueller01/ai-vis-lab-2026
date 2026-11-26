"""TiRex-2 inference, validation and paired Phase II interventions."""

import json
import subprocess
from contextlib import nullcontext
from hashlib import file_digest
from importlib.metadata import distribution
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlparse

import numpy as np
import pandas as pd
import torch
from pilot_cases import CONTEXT, HORIZON, LONG
from tirex2 import TimeseriesType, load_model
from tirex2_internal_maps import (
    CHECKPOINT_REVISION,
    differentiable_forecast,
    gate_saliency,
    input_saliency,
    memory_flow,
    temporal_coefficients,
    trace_mlstm,
    trace_slstm,
)

SOURCE_REVISION = "9e9d19a1767845e986a084924ddb64eb1aa1c49a"
PATCH = 32
COUNTS = (1, 2, 4, 8, 12, 16)
AMPLITUDES = (3, 6, 9, 12, 15)
PULSE_AGES = np.arange(22, 76)
Q = [0, 4, 8]
SHIFT = 24
CHECKPOINT_SHA256 = {
    "config.json": "e591152ebc5bd7245b5258cd26a52b57c1f6cfe60d6743111856ab0b12f7425e",
    "model.safetensors": "17760e4eee4c14e0d8bad8b9d9ce6f5076aaeeb9d956a88b8e95cf1493a1c176",
}


def verify_pins(checkpoint):
    install = json.loads(distribution("tirex-2").read_text("direct_url.json") or "{}")
    revision = install.get("vcs_info", {}).get("commit_id")
    url = urlparse(install.get("url", ""))
    if revision is None and url.scheme == "file":
        source = Path(unquote(url.path))
        if (source / ".git").exists():
            revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            changed = subprocess.check_output(
                ["git", "-C", str(source), "status", "--porcelain", "--", "src"], text=True
            )
            if changed:
                raise RuntimeError(f"Modified TiRex-2 sources in {source}")
    if revision != SOURCE_REVISION:
        raise RuntimeError(f"Install TiRex-2 from source revision {SOURCE_REVISION}")
    for filename, expected in CHECKPOINT_SHA256.items():
        with (checkpoint / filename).open("rb") as file:
            actual = file_digest(file, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError(f"Unexpected SHA-256 for {checkpoint / filename}")


class Model:
    def __init__(self, checkpoint, batch_size):
        verify_pins(checkpoint)
        self.wrapper = load_model(str(checkpoint), device="cpu", compile=False, cuda_graphs=False)
        self.net = self.wrapper.model.eval().requires_grad_(False)
        self.batch_size = batch_size
        self.slstm = self.net.stack[1].time_mixer.fwd_cell
        self.mlstm = self.net.stack[0].time_mixer.fwd_cell
        assert self.net.quantiles[Q].tolist() == torch.tensor([0.1, 0.5, 0.9]).tolist()
        assert not self.net.tta_sign_flip

    def settings(self):
        return {
            "source_revision": SOURCE_REVISION,
            "checkpoint_revision": CHECKPOINT_REVISION,
            "torch": torch.__version__,
            "pad_context": True,
            "context_capacity": self.net.context_len,
            "padding_hours_at_672": self.net.context_len - CONTEXT,
            "future_padding": self.net.future_len,
            "tta_diff": self.net.tta_diff,
            "tta_sign_flip": False,
            "compile": False,
            "cuda_graphs": False,
            "patch_size": PATCH,
            "forecast_batch_size": self.batch_size,
            "torch_threads": torch.get_num_threads(),
        }

    @staticmethod
    def series(x, past=None, future=None):
        t = lambda a: None if a is None else torch.from_numpy(np.ascontiguousarray(a, dtype=np.float32))
        return TimeseriesType(t(x[None]), t(past), t(future))

    def forecast(self, series, quantiles=Q):
        """Use the public wrapper and capture the realized target differencing branch."""
        post = self.net.postprocessor
        original = post.transform_input
        diff = []

        def capture(*args, **kwargs):
            batch, args, kwargs = original(*args, **kwargs)
            diff.extend(mask[0] for mask in kwargs["diff_masks"])
            return batch, args, kwargs

        with patch.object(post, "transform_input", capture):
            out = self.wrapper.forecast(
                series,
                prediction_length=HORIZON,
                output_type="numpy",
                batch_size=self.batch_size,
                pad_context=True,
                tta_sign_flip=False,
                tta_diff=self.net.tta_diff,
            )
        return np.stack(out)[:, 0][:, quantiles], np.asarray(diff, dtype=bool)

    def mapping(self):
        net = self.net
        assert (net.input_patch_size, net.output_patch_size, net.tokenizer.input_patch_stride) == (PATCH,) * 3
        lag = -torch.arange(CONTEXT, 0, -1, dtype=torch.float32)
        prepared = net._fix_context_size(
            HORIZON, torch.nn.functional.pad(lag[None], (0, HORIZON), value=torch.nan), True
        )
        patches, state = net.tokenizer.input_transform(prepared)
        count = state["len"]
        receiver = count - net.future_len // PATCH - 1
        torch.testing.assert_close(patches[0, receiver], -torch.arange(PATCH, 0, -1, dtype=torch.float32))
        tokens = torch.arange(count, dtype=torch.float32).view(1, 1, count, 1).expand(1, 1, count, PATCH)
        output = net.tokenizer.output_transform(tokens, state)[..., :-PATCH][..., -net.future_len :][..., :HORIZON]
        assert (output == receiver).all()
        starts = (np.arange(count) - receiver) * PATCH - PATCH
        return receiver, starts

    def gradients(self, x, trace=False, verify=False):
        t = self.series(x).target.requires_grad_()
        with (
            trace_slstm(self.slstm) if trace else nullcontext() as slstm,
            trace_mlstm(self.mlstm) if trace else nullcontext() as mlstm,
        ):
            forecast = differentiable_forecast(self.net, t)
        median = input_saliency(forecast, t, Q[1])[:, 0]
        width = input_saliency(forecast[:, 8:9] - forecast[:, 0:1], t, 0)[:, 0]
        if not torch.isfinite(median[:, t[0].isfinite()]).all() or not torch.isfinite(width[:, t[0].isfinite()]).all():
            raise RuntimeError("Nonfinite gradients for observed inputs")
        result = {"median_grad": median.numpy()[:, ::-1], "width_grad": width.numpy()[:, ::-1]}
        if trace:
            scores = [forecast[0, 4, 5], forecast[0, 4, 23], forecast[0, 4, 23] - forecast[0, 4, 0]]
            result["gates"] = torch.stack([gate_saliency(score, slstm[0]) for score in scores]).numpy()
            flow, hidden = memory_flow(slstm[0])
            coefficients = temporal_coefficients(mlstm[0])
            result.update(memory=flow.numpy(), coefficients=coefficients[0].numpy())
            if verify:
                torch.testing.assert_close(
                    hidden, torch.stack([s["y"][0].detach() for s in slstm[0]]), rtol=3e-4, atol=3e-4
                )
                torch.testing.assert_close(coefficients @ mlstm[0]["v"], mlstm[0]["h"], rtol=3e-3, atol=3e-3)
        if verify:
            stock, branch = self.forecast([self.series(x)], quantiles=slice(None))
            np.testing.assert_allclose(forecast.detach().numpy()[0], stock[0], rtol=3e-4, atol=3e-4)
            result["parity_max_abs_c"] = float(np.max(np.abs(forecast.detach().numpy()[0] - stock[0])))
            result["diff"] = bool(branch[0])
        return result

    def lag_interventions(self, history):
        # Run in blocks so the large inference batch is bounded by --batch-size.
        result = {}
        for method, deltas in [("mask", [np.nan]), ("fd025", [-0.25, 0.25]), ("fd1", [-1.0, 1.0])]:
            forecasts, branches = [], []
            for delta in deltas:
                values = np.broadcast_to(history, (CONTEXT, CONTEXT)).copy()
                row = np.arange(CONTEXT)
                values[row, CONTEXT - 1 - row] += delta
                fc, diff = self.forecast([self.series(x) for x in values])
                forecasts.append(fc[:, 1].T)
                branches.append(diff)
            result[f"{method}_forecasts"] = np.stack(forecasts)
            result[f"{method}_diff"] = np.stack(branches)
        return result

    @torch.no_grad()
    def embeddings(self, history, receiver):
        # Equal scaled changes to each value slot of the same older token,
        # with its baseline and the 32 presence indicators fixed.
        samples = [self.series(history)]
        for slot in range(PATCH):
            x = history.copy()
            x[-2 * PATCH + slot] += 1
            samples.append(self.series(x))
        _, batch, _, _ = self.net._prepare_input(samples, HORIZON, self.net.tta_diff, pad_context=True)
        embedded = []

        def capture(_, args, output):
            embedded.extend((args[0].detach(), output.detach()))

        with self.net.input_patch_embedding.register_forward_hook(capture):
            self.net._prepare_forward(batch)
        inputs, tokens = embedded
        token = receiver - 1
        base = inputs[0, token].repeat(PATCH, 1)
        base += torch.eye(PATCH, 2 * PATCH) * 0.25
        direct = self.net.input_patch_embedding(base) - tokens[0, token]
        return {
            "embed_direct": direct.flip((0,)).numpy(),
            "embed_input_weather": (inputs[1:] - inputs[0]).flip((0,)).numpy(),
            "embed_tokens_weather": (tokens[1:] - tokens[0]).flip((0,)).numpy(),
        }


def pulse_histories(history):
    pulse = -4 * np.hanning(17).astype(np.float32)
    for age in PULSE_AGES:
        x = history.copy()
        k = len(x) - age
        x[k - 8 : k + 9] += pulse
        yield x


def level_slope(history, offset):
    """Vary the warm prefix and flatten the latest slope, retaining the last value."""
    cold = max(1, int(offset))
    prefix = np.ones(len(history), np.float32)
    prefix[-cold:] = 0
    prefix[-cold - 6 : -cold] = np.linspace(1, 0, 6, endpoint=False)
    hours = np.arange(-5, 1)
    slope = np.polyfit(hours, history[-6:], 1)[0]
    flattened = history.copy()
    # Remove the fitted slope and taper the transition over the previous six hours.
    flattened[-6:] -= (slope * hours).astype(np.float32)
    flattened[-12:-6] += np.linspace(0, 5 * slope, 6, endpoint=False, dtype=np.float32)
    return [history - 3 * prefix, history + 3 * prefix, flattened], slope


def sweep_histories(history, shape):
    yield history
    faded = shape.copy()
    faded[-12:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, 12)))
    for profile in (shape, faded):
        for count in COUNTS:
            for delta in AMPLITUDES:
                x = history.copy()
                for start in np.linspace(168, LONG - 24 - len(shape), count).astype(int):
                    x[start : start + len(shape)] += delta * profile
                yield x


def change3(values):
    result = np.full_like(values, np.nan)
    result[3:] = values[3:] - values[:-3]
    return result


class Covariates:
    def __init__(self, weather):
        # Past covariates never interpolate from rows after the feature timestamp.
        data = pd.read_parquet(weather.directory / "grid_long.parquet", columns=["point_id", "time", "P0", "UU", "VV"])
        fields = {
            name: data.pivot(index="time", columns="point_id", values=name).to_numpy(np.float32)
            for name in ("P0", "UU", "VV")
        }
        self.weather = weather
        self.pressure = change3(fields["P0"] / 100)
        self.temp_change = change3(weather.raw)
        self.wind_from = np.degrees(np.arctan2(-fields["UU"], -fields["VV"])) % 360
        self.wind_from[np.hypot(fields["UU"], fields["VV"]) == 0] = np.nan
        xy = weather.points[["x", "y"]].to_numpy() / 1000
        x, y = (xy[None] - xy[:, None]).transpose(2, 0, 1)
        self.distance = np.hypot(x, y)
        self.bearing = np.degrees(np.arctan2(x, y)) % 360

    def rows(self, case, length, shift=0):
        c = self.weather.columns[case.point_id]
        hours = np.arange(case.o - length - shift, case.o - shift)
        dist, bearing = self.distance[c], self.bearing[c]
        up = (bearing >= 290) | (bearing <= 20)
        rings = [np.flatnonzero(up & (dist >= low) & (dist < high)) for low, high in [(40, 120), (120, 240)]]
        phase1 = np.array(
            [self.temp_change[np.ix_(hours, ring)].mean(1) if len(ring) else np.zeros(length) for ring in rings],
            dtype=np.float32,
        )
        # Order candidates by distance so the first eligible point is the nearest.
        neighbors = np.flatnonzero((dist > 0) & (dist <= 60))
        neighbors = neighbors[np.argsort(dist[neighbors], kind="stable")]
        difference = (bearing[neighbors] - self.wind_from[hours, c, None] + 180) % 360 - 180
        eligible = np.abs(difference) <= 45
        chosen = np.full(length, -1)
        valid = eligible.any(1)
        if valid.any():
            chosen[valid] = neighbors[eligible[valid].argmax(1)]
        aligned = np.full((2, length), np.nan, dtype=np.float32)
        time = hours[valid]
        point = chosen[valid]
        aligned[0, valid] = self.weather.raw[time, point] - self.weather.raw[time, c]
        aligned[1, valid] = self.temp_change[time, point]
        pressure = self.pressure[hours, c][None]
        return pressure, phase1, aligned, chosen


def covariate_interventions(model, weather, covariates, row):
    result = {}
    for length, suffix in [(CONTEXT, ""), (LONG, "_exp4")]:
        history = weather.history(row, length)
        now = covariates.rows(row, length)
        shifted = covariates.rows(row, length, SHIFT)
        configs = (
            [(1, "phase1")]
            if length == LONG
            else [
                (0, "pressure"),
                (1, "phase1"),
                (2, "wind"),
                (2, "wind_difference"),
                (2, "wind_change"),
            ]
        )
        for idx, name in configs:
            actual, control = now[idx], shifted[idx]
            if name == "wind_difference":
                actual, control = actual[:1], control[:1]
            if name == "wind_change":
                actual, control = actual[1:], control[1:]
            if idx == 1:
                # Exp 4 scaled each series, with absent rings represented by zero.
                actual, control = [np.nan_to_num(x) for x in (actual, control)]
                actual, control = [
                    (x - x.mean(1, keepdims=True)) / x.std(1, keepdims=True).clip(0.001) for x in (actual, control)
                ]
            if idx == 2:
                # Use identical support so the time-shift comparison isolates feature timing.
                common = np.isfinite(actual) & np.isfinite(control)
                actual, control = np.where(common, actual, np.nan), np.where(common, control, np.nan)
            scales = np.array([np.std(x[np.isfinite(x)]) if np.isfinite(x).any() else 0 for x in actual])
            ts = [model.series(history, p) for p in (None, actual, control)]
            for k, scale in enumerate(scales):
                for sign in (-1, 1):
                    perturbed = actual.copy()
                    perturbed[k, -24:] += sign * 0.5 * scale
                    ts.append(model.series(history, perturbed))
            forecasts, diff = model.forecast(ts)
            series = model.series(history, actual)
            t, past = series.target, series.past_covariates
            past.requires_grad_()
            forecast = differentiable_forecast(model.net, t, past_covariates=past)
            grad = input_saliency(forecast, past, 4).numpy() * scales[None, :, None]
            if not np.isfinite(grad[:, np.isfinite(actual)]).all():
                raise RuntimeError(f"Nonfinite observed covariate gradient: {name}")
            key = name + suffix
            result.update(
                {
                    f"{key}_forecasts": forecasts,
                    f"{key}_diff": diff,
                    f"{key}_grad": grad,
                    f"{key}_scale": scales,
                    f"{key}_inputs": actual,
                    f"{key}_control": control,
                }
            )
        if length == CONTEXT:
            result["wind_point"], result["wind_control_point"] = [
                np.where(x[-1] >= 0, weather.point_ids[x[-1]], -1) for x in [now, shifted]
            ]
    return result


def synthetic_flags(model):
    counts = np.array([0, 1, 2, 4, 8, 12, 16])
    series = []
    hours = np.arange(LONG + HORIZON)
    for count in counts:
        history = (12 + 2 * np.sin(2 * np.pi * hours[:LONG] / 24)).astype(np.float32)
        prior = np.zeros((1, len(hours)), np.float32)
        if count:
            for start in np.linspace(130, LONG - 96, count).astype(int):
                history[start : start + 42] -= 6 * np.hanning(84)[42:]
                prior[0, start - 12 : start] = 1
        for flag in (0, 1):
            # The front begins at forecast hour +13, giving 12 known warning hours.
            known = prior.copy()
            known[0, LONG : LONG + 12] = flag
            series.append(model.series(history, future=known))
    forecast, diff = model.forecast(series)
    return {
        "counts": counts,
        "forecast": forecast.reshape(len(counts), 2, 3, HORIZON),
        "diff": diff.reshape(len(counts), 2),
    }


def run_case(model, weather, row, receiver, shape, covariates, *, pilot):
    x = weather.history(row)
    is_exp10 = isinstance(row.exp10, str) and row.exp10 in ("ordinary", "pre-front")
    trace = bool(row.aligned) or (pilot and row.pilot_order == 0)
    result = model.gradients(x, trace=trace)
    base, branch = model.forecast([model.series(x)])
    result.update(history=x, truth=weather.truth(row), forecast=base[0], base_diff=branch[0])
    if is_exp10:
        result.update(model.lag_interventions(x))
    if row.pulse:
        result["pulse_forecast"], result["pulse_diff"] = model.forecast([model.series(y) for y in pulse_histories(x)])
        result.update(model.embeddings(x, receiver))
    if (row.aligned or pilot) and np.isfinite(row.offset) and row.offset >= 3:
        histories, slope = level_slope(x, row.offset)
        result["level_slope_forecast"], result["level_slope_diff"] = model.forecast(
            [model.series(y) for y in histories]
        )
        result["level_slope_inputs"], result["recent_slope"] = np.stack(histories), slope
    if row.sweep:
        history = weather.history(row, LONG)
        result["sweep_forecast"], result["sweep_diff"] = model.forecast(
            [model.series(y) for y in sweep_histories(history, shape)]
        )
        result["sweep_history"] = history
    if row.upstream:
        result.update(covariate_interventions(model, weather, covariates, row))
    return result
