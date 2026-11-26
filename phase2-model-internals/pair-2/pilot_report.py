"""Render Phase II plots and export weather-block estimates for uncertainty."""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LEADS = np.arange(1, 25)
LAGS = np.arange(1, 673)
SLOTS = np.arange(1, 33)
COHORTS = ("cooling", "stable", "warming")


def baseline(weather, candidates):
    """Paired lead skill from the saved forecasts, grouped for block resampling."""
    rows = []
    for (block, cohort), group in candidates.groupby(["block", "cohort"]):
        origins = group.o.to_numpy()[:, None] + np.arange(24)
        points = group.point_id.map(weather.columns).to_numpy()[:, None]
        past = weather.raw[origins - 24, points]
        truth = weather.raw[origins, points]
        median = weather.cache[group.saved_run, group.saved_point, 4].astype(np.float32)
        mask = np.isfinite(past) & np.isfinite(truth) & np.isfinite(median)
        rows.append(
            pd.DataFrame(
                {
                    "block": block,
                    "cohort": cohort,
                    "lead": LEADS,
                    "cases": len(group),
                    "n": mask.sum(0),
                    "model_abs_sum": np.where(mask, np.abs(median - truth), 0).sum(0),
                    "baseline_abs_sum": np.where(mask, np.abs(past - truth), 0).sum(0),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def curve(ax, values, x, label, *, color=None, style="-"):
    ax.plot(x, np.nanmean(values, axis=0), style, label=label, color=color)


def image(ax, values, title, *, limit=None, signed=False, extent=None):
    options = (
        {"cmap": "RdBu_r", "vmin": -limit, "vmax": limit} if signed else {"cmap": "magma", "vmin": 0, "vmax": limit}
    )
    heat = ax.imshow(values, aspect="auto", origin="lower", interpolation="nearest", extent=extent, **options)
    ax.set_title(title)
    ax.figure.colorbar(heat, ax=ax, shrink=0.8)


def save_figure(fig, path):
    fig.savefig(path, dpi=145, bbox_inches="tight")
    plt.close(fig)


def metric(panel, group, setup, lead, block, value):
    return {"panel": panel, "group": group, "setup": setup, "lead": lead, "block": block, "value": value}


def profile(values, exclude=0):
    """Lead × lag with lag 1 first. Mean within each slot among eligible hours."""
    values = np.abs(values.copy())
    values[..., :exclude] = np.nan
    folded = values.reshape(*values.shape[:-1], 21, 32)
    return np.nanmean(folded, axis=-2)


def ratio(values):
    return np.nanmean(values[..., :2], axis=-1) / np.nanmean(values, axis=-1)


def share(values):
    total = np.nansum(values, axis=-1, keepdims=True)
    return np.divide(values, total, out=np.zeros_like(values), where=total > 0)


def records(cases, out, manifest_id):
    result = []
    for case in cases.itertuples():
        path = out / "arrays" / f"{case.case_id}.npz"
        if path.exists():
            with np.load(path) as arrays:
                if arrays["manifest_id"].item() != manifest_id:
                    raise ValueError(f"Stale case archive {path}")
                result.append((case, dict(arrays)))
    return result


def clustered(frame, keys):
    """Resample entire events/blocks and retain their original point estimates."""
    if frame.empty:
        return pd.DataFrame(), pd.DataFrame()
    blocks = frame.groupby([*keys, "block"], dropna=False).value.agg(["mean", "size"]).reset_index()
    summaries = []
    rng = np.random.default_rng(2026)
    for key, group in blocks.groupby(keys, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        means = group["mean"].to_numpy()
        counts = group["size"].to_numpy()
        samples = rng.integers(len(group), size=(1000, len(group)))
        bootstrap = means[samples].mean(1)
        low, high = np.quantile(bootstrap, [0.025, 0.975]) if len(group) >= 3 else (np.nan, np.nan)
        summaries.append(
            dict(
                zip(keys, key),
                n=int(counts.sum()),
                blocks=len(group),
                estimate=means.mean(),
                low=low,
                high=high,
                sparse=len(group) < 3,
            )
        )
    return blocks, pd.DataFrame(summaries)


def patch_magnitude(data, name):
    if name == "gradient":
        return data["median_grad"]
    values = data[f"{name}_forecasts"]
    if name == "mask":
        return values[0] - data["forecast"][1, :, None]
    return (values[1] - values[0]) / (0.5 if name == "fd025" else 2.0)


METHODS = ("gradient", "mask", "fd025", "fd1")
METHOD_NAMES = dict(zip(METHODS, ("Gradient", "NaN mask", "±0.25 °C slope", "±1 °C slope")))


def patch_panels(rows, directory, metrics):
    exp = [(r, d) for r, d in rows if "mask_forecasts" in d]
    if not exp:
        return
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    signed = np.nanmean([d["median_grad"] for _, d in exp], axis=0)
    absolute = np.nanmean([np.abs(d["median_grad"]) for _, d in exp], axis=0)
    image(
        axes[0, 0],
        signed,
        "Signed q50 derivative",
        limit=np.max(np.abs(signed)),
        signed=True,
        extent=(0.5, 672.5, 0.5, 24.5),
    )
    image(axes[0, 1], profile(absolute), "Mean absolute derivative by lead", extent=(0.5, 32.5, 0.5, 24.5))
    patch_age = absolute.reshape(24, 21, 32).mean(0)
    image(axes[1, 0], patch_age, "Mean absolute derivative by patch age", extent=(0.5, 32.5, -0.5, 20.5))
    image(axes[1, 1], share(patch_age), "Share of total sensitivity within each patch", extent=(0.5, 32.5, -0.5, 20.5))
    for ax, x, y in zip(
        axes.ravel(),
        ("Input lag (hours)", "Slot from newest", "Slot from newest", "Slot from newest"),
        ("Forecast lead (hours)", "Forecast lead (hours)", "Patch age", "Patch age"),
    ):
        ax.set(xlabel=x, ylabel=y)
    fig.suptitle(f"1. Hourly sensitivity on the 32-hour grid (n={len(exp)})")
    save_figure(fig, directory / "01_patch_heatmaps.png")

    fig, axes = plt.subplots(3, 4, figsize=(15, 9), sharex=True, sharey="row", layout="constrained")
    for r, d in exp:
        for exclude in (24, 32):
            masked = ratio(profile(patch_magnitude(d, "mask"), exclude).mean(0))
            metrics.append(metric("mask ratio above one", r.exp10, "mask", exclude, r.block, float(masked > 1)))
            for name in ("gradient", "fd025", "fd1"):
                effect = ratio(profile(patch_magnitude(d, name), exclude).mean(0))
                metrics.append(
                    metric("patch ratio difference vs mask", r.exp10, name, exclude, r.block, effect - masked)
                )
    for col, method in enumerate(METHODS):
        for ax, exclude in zip(axes[:, col], (0, 24, 32)):
            for group, color in [("ordinary", "#426a93"), ("pre-front", "#bb5138")]:
                subset = [(r, d) for r, d in exp if r.exp10 == group]
                if not subset:
                    continue
                folded = np.array([profile(patch_magnitude(d, method), exclude).mean(0) for _, d in subset])
                curve(ax, share(folded), SLOTS, f"{group} (n={len(subset)})", color=color)
                for (r, _), value in zip(subset, ratio(folded)):
                    metrics.append(metric("patch ratio", group, method, exclude, r.block, value))
                for (r, _), value in zip(subset, folded.mean(1)):
                    metrics.append(metric("patch raw sensitivity", group, method, exclude, r.block, value))
                if method != "gradient":
                    for r, d in subset:
                        changed = (d[f"{method}_diff"][:, exclude:] != d["base_diff"]).mean()
                        metrics.append(metric("patch branch change", group, method, exclude, r.block, changed))
            ax.axhline(1 / 32, color=".6", lw=0.7)
            ax.set_title(f"{METHOD_NAMES[method]} · omit {exclude} h")
    axes[0, 0].legend(fontsize=8)
    fig.supxlabel("Slot from newest")
    fig.supylabel("Share of within-patch sensitivity")
    fig.suptitle("2. Perturbation controls on identical weather cases")
    save_figure(fig, directory / "02_patch_controls.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True, layout="constrained")
    for ax, key in zip(axes, ["season", "region"]):
        for name in sorted({getattr(r, key) for r, _ in exp}):
            subset = [(r, d) for r, d in exp if getattr(r, key) == name]
            curves = np.array([profile(d["median_grad"], 32).mean(0) for _, d in subset])
            block_count = len({r.block for r, _ in subset})
            sparse = " · sparse" if block_count < 3 else ""
            curve(ax, share(curves), SLOTS, f"{name} (n={len(subset)}, blocks={block_count}){sparse}")
            for (r, _), value in zip(subset, ratio(curves)):
                metrics.append(metric("gradient strata", f"{key} {name}", "gradient", 32, r.block, value))
        ax.set(xlabel="Slot from newest", title=key.capitalize())
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Share of within-patch sensitivity")
    save_figure(fig, directory / "02_patch_strata.png")

    subset = [(r, d) for r, d in exp if "pulse_forecast" in d]
    if not subset:
        return
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    for lead in (1, 6, 24):
        response = [d["pulse_forecast"][:, 1, lead - 1] - d["forecast"][1, lead - 1] for _, d in subset]
        ages = np.arange(22, 76)
        curve(axes[0], response, ages, f"+{lead} h")
        for (r, _), values in zip(subset, response):
            for age, value in zip(ages, values):
                metrics.append(metric("pulse response", r.exp10, f"lead +{lead} h", age, r.block, value))
    for edge in [32.5, 64.5]:
        axes[0].axvline(edge, color=".5", ls="--")
    axes[0].set(
        xlabel="Pulse center lag (hours)", ylabel="Change in q50 (°C)", title=f"Smooth cooling pulse (n={len(subset)})"
    )
    axes[0].legend()
    direct = [np.linalg.norm(d["embed_direct"], axis=-1) for _, d in subset]
    curve(axes[1], direct, SLOTS, "Equal scaled perturbation")
    axes[1].set(xlabel="Slot from newest", ylabel="Embedding output change (L2)", title="Controlled embedding input")
    weather = [np.linalg.norm(d["embed_tokens_weather"][:, int(d["receiver"]) - 1], axis=-1) for _, d in subset]
    inputs = [np.linalg.norm(d["embed_input_weather"][:, int(d["receiver"]) - 1], axis=-1) for _, d in subset]
    for (r, _), controlled, actual in zip(subset, direct, weather):
        metrics.extend(
            [
                metric("embedding newest-two ratio", r.exp10, "equal scaled input", 0, r.block, ratio(controlled)),
                metric("embedding newest-two ratio", r.exp10, "1 °C weather input", 0, r.block, ratio(actual)),
            ]
        )
    curve(axes[2], weather, SLOTS, "Token change")
    ax_input = axes[2].twinx()
    curve(ax_input, inputs, SLOTS, "Embedding input change", color="#b04c35", style="--")
    axes[2].set(xlabel="Slot from newest", ylabel="Token change (L2)", title="1 °C perturbation in the weather input")
    ax_input.set_ylabel("Scaled input change (L2)", color="#b04c35")
    save_figure(fig, directory / "02_pulse_embedding.png")


def front_panels(rows, directory, metrics):
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), layout="constrained", sharex=True, sharey=True)
    aligned = [(r, d) for r, d in rows if r.aligned]
    for offset, ax in zip((-6, 0, 3, 6, 12), axes.ravel()):
        subset = [(r, d) for r, d in aligned if r.offset == offset]
        if not subset:
            ax.set_title(f"Issued {offset:+} h (n=0)")
            continue
        valid = [(r, d) for r, d in subset if np.isfinite(d["history"][-6:]).all()]
        hours = offset + np.arange(24)
        curve(ax, [d["truth"] for _, d in subset], hours, "Observed", color="#20242b")
        curve(ax, [d["history"][-24:] for _, d in subset], offset + np.arange(-24, 0), None, color="#20242b")
        fc = np.mean([d["forecast"] for _, d in subset], axis=0)
        ax.fill_between(hours, fc[0], fc[2], color="#699dc9", alpha=0.28, label="q10–q90")
        ax.plot(hours, fc[1], label="q50", color="#376d9b")
        ax.axhline(np.mean([d["history"][-1] for _, d in subset]), color="#8f571f", ls="--", label="Last value")
        if valid:
            curve(
                ax,
                [d["history"][-1] + np.polyfit(np.arange(-5, 1), d["history"][-6:], 1)[0] * LEADS for _, d in valid],
                hours,
                "Recent slope",
                color="#b34c3d",
                style=":",
            )
        ax.axvline(0, color=".5", lw=0.8)
        ax.set_title(f"Issued {offset:+} h (n={len(subset)})")
        for r, d in subset:
            last = d["history"][-1]
            slope = np.polyfit(np.arange(-5, 1), d["history"][-6:], 1)[0]
            for name, values in [
                ("observed", d["truth"]),
                ("q50", d["forecast"][1]),
                ("persistence", np.full(24, last)),
                ("recent slope", last + LEADS * slope),
            ]:
                for lead, value in zip(LEADS, values - last):
                    metrics.append(metric("front aligned change", f"issued {offset:+} h", name, lead, r.block, value))
    handles = next((ax.get_legend_handles_labels() for ax in axes.ravel() if ax.lines), ([], []))
    axes[-1, -1].axis("off")
    axes[-1, -1].legend(*handles, loc="center")
    fig.suptitle("3. Forecasts aligned to the local front passage")
    fig.supxlabel("Hours relative to local passage")
    fig.supylabel("Temperature (°C)")
    if aligned:
        save_figure(fig, directory / "03_front_alignment.png")
    else:
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharex=True, sharey=True, layout="constrained")
    for cohort, ax in zip(COHORTS, axes):
        subset = [(r, d) for r, d in rows if r.cohort == cohort and r.skill_case]
        ax.set_title(f"{cohort.capitalize()} (n={len(subset)})")
        if not subset:
            continue
        for name, field in [("Observed", "truth"), ("Forecast q50", "forecast")]:
            changes = np.array([(d[field] if field == "truth" else d[field][1]) - d["history"][-1] for _, d in subset])
            curve(ax, changes, LEADS, name)
            for (r, _), change in zip(subset, changes):
                for lead, value in zip(LEADS, change):
                    metrics.append(metric("change", cohort, name, lead, r.block, value))
        ax.axhline(0, color=".6", lw=0.7)
        ax.legend()
    fig.supxlabel("Forecast lead (hours)")
    fig.supylabel("Change from last observation (°C)")
    save_figure(fig, directory / "03_change_cohorts.png")

    interventions = [(r, d) for r, d in rows if "level_slope_forecast" in d]
    if interventions:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
        names = ["Warm prefix −3 °C", "Warm prefix +3 °C", "Remove recent slope"]
        for k, name in enumerate(names):
            effects = np.array([d["level_slope_forecast"][k, 1] - d["forecast"][1] for _, d in interventions])
            curve(axes[0], effects, LEADS, name)
            axes[1].scatter(np.mean(effects, 1), effects[:, -1] - effects[:, 0], s=18, alpha=0.7, label=name)
            for (r, _), effect in zip(interventions, effects):
                for panel, value in [
                    ("forecast level response", effect.mean()),
                    ("forecast swing response", effect[-1] - effect[0]),
                ]:
                    metrics.append(metric(panel, f"passage {r.offset:+g} h", name, 24, r.block, value))
        axes[0].set(xlabel="Forecast lead (hours)", ylabel="Paired q50 response (°C)")
        axes[1].set(xlabel="Paired mean q50 response (°C)", ylabel="Paired forecast swing response (°C)")
        axes[0].legend(fontsize=8)
        axes[1].axhline(0, color=".6", lw=0.7)
        fig.suptitle(f"3. Warm level and recent slope interventions (n={len(interventions)})")
        save_figure(fig, directory / "03_level_slope.png")

    traced = [(r, d) for r, d in rows if "gates" in d]
    if traced:
        preferred = [(r, d) for r, d in traced if r.aligned]
        r, d = (preferred or traced)[0]
        start, receiver = int(d["receiver"]) - 20, int(d["receiver"])
        span = slice(start, receiver + 1)
        fig, axes = plt.subplots(1, 4, figsize=(15, 3.6), layout="constrained")
        gate_limit = max(float(d["gates"].max()), 1e-10)
        for k, label in enumerate(["q50 +6 h", "q50 +24 h", "q50 swing"]):
            image(
                axes[k],
                d["gates"][k, :, span],
                label,
                limit=gate_limit,
                extent=(start - 0.5, receiver + 0.5, -0.5, 3.5),
            )
            axes[k].set(yticks=range(4), yticklabels=["Input", "Forget", "Candidate", "Output"], xlabel="32-hour token")
        image(
            axes[3],
            d["memory"][span, span],
            "sLSTM realized memory",
            extent=(start - 0.5, receiver + 0.5, start - 0.5, receiver + 0.5),
        )
        axes[3].set(xlabel="Source token", ylabel="Receiver token")
        fig.suptitle(f"3. Native internal maps · case {r.case_id} · layers 1 (sLSTM) and 0 (mLSTM)")
        save_figure(fig, directory / "03_internal_gates.png")
        count = len(d["coefficients"])
        fig, axes = plt.subplots(2, (count + 1) // 2, figsize=(13, 7), layout="constrained", squeeze=False)
        limit = np.percentile(np.abs(d["coefficients"][:, span, span]), 99)
        for k, ax in enumerate(axes.ravel()):
            if k >= count:
                ax.set_axis_off()
                continue
            image(
                ax,
                d["coefficients"][k, span, span],
                f"Head {k}",
                limit=limit,
                signed=True,
                extent=(start - 0.5, receiver + 0.5, start - 0.5, receiver + 0.5),
            )
        fig.supxlabel("Source token (32 hours)")
        fig.supylabel("Receiver token (32 hours)")
        fig.suptitle(f"3. Signed mLSTM temporal coefficients · case {r.case_id}")
        save_figure(fig, directory / "03_internal_heads.png")


def interval_panels(rows, directory, metrics):
    phases = {name: [] for name in ("stable", "before", "during", "after")}
    count = {name: set() for name in phases}
    saliency = {name: [[], []] for name in ("covered", "missed")}
    fixed = 11
    for r, d in rows:
        if r.aligned or r.offset == -6:
            phase = "before" if r.offset < -2 else "during" if r.offset <= 3 else "after"
        elif r.skill_case and r.cohort == "stable":
            phase = "stable"
        else:
            continue
        q10, q50, q90 = d["forecast"]
        for j, truth in enumerate(d["truth"]):
            if not np.isfinite(truth):
                continue
            below, above = truth < q10[j], truth > q90[j]
            values = [q90[j] - q10[j], q50[j] - truth, below, not (below or above), above]
            phases[phase].append((j + 1, values))
            count[phase].add(r.case_id)
            for panel, value in zip(("width", "median bias", "below", "inside", "above"), values):
                metrics.append(metric(panel, phase, "base", j + 1, r.block, float(value)))
            if j == fixed and phase != "stable":
                covered = "missed" if below or above else "covered"
                for i, key in enumerate(("median_grad", "width_grad")):
                    saliency[covered][i].append(np.abs(d[key][j]))
                    metrics.append(
                        metric("interval sensitivity", covered, key, j + 1, r.block, np.abs(d[key][j]).mean())
                    )
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), sharex=True, layout="constrained")
    for phase, pairs in phases.items():
        if not pairs:
            continue
        frame = pd.DataFrame([[j, *v] for j, v in pairs], columns=["lead", 0, 1, 2, 3, 4])
        avg = frame.groupby("lead").mean().reindex(LEADS)
        for i, ax in enumerate(axes.ravel()[:5]):
            ax.plot(LEADS, avg[i], label=f"{phase} (n={len(count[phase])})")
    for ax, name in zip(axes.ravel(), ("Interval width (°C)", "Median error (°C)", "Below q10", "Inside", "Above q90")):
        ax.set_title(name)
    axes[1, 1].axhline(0.8, color=".6", lw=0.7)
    axes[1, 2].axis("off")
    axes[1, 2].legend(*axes[0, 0].get_legend_handles_labels(), loc="center")
    fig.supxlabel("Forecast lead (hours)")
    fig.suptitle("4. Interval width, bias and coverage by issuance relative to passage")
    save_figure(fig, directory / "04_coverage.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for i, (ax, target) in enumerate(zip(axes, ("q50", "q90 − q10"))):
        for group, values in saliency.items():
            if values[i]:
                curve(ax, values[i], LAGS, f"{group} (n={len(values[i])})")
        ax.set(xlabel="Input lag (hours)", ylabel="Mean absolute derivative", title=f"{target} sensitivity at +12 h")
        if ax.lines:
            ax.legend()
    save_figure(fig, directory / "04_coverage_saliency.png")

    sweep = [(r, d) for r, d in rows if "sweep_forecast" in d]
    if not sweep:
        return
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained", sharex=True)
    amplitudes = [0, 3, 6, 9, 12, 15]
    colors = plt.cm.viridis(np.linspace(0.1, 0.85, 6))
    for r, d in sweep:
        baseline, values = d["sweep_forecast"][0], d["sweep_forecast"][1:].reshape(2, 6, 5, 3, 24)
        for sel, kind in enumerate(("abrupt", "faded")):
            branch = d["sweep_diff"][1:].reshape(2, 6, 5)[sel]
            for i, count in enumerate((1, 2, 4, 8, 12, 16)):
                for j, amp in enumerate(amplitudes[1:]):
                    f = values[sel, i, j]
                    for k, name in enumerate(("q10", "q50", "q90", "width")):
                        value = f[k].mean() if k < 3 else (f[2] - f[0]).mean()
                        metrics.append(metric(f"Exp 6 {name}", f"{count} drops", kind, amp, r.block, value))
                    paired_width = ((f[2] - f[0]) - (baseline[2] - baseline[0])).mean()
                    metrics.append(metric("Exp 6 width change", f"{count} drops", kind, amp, r.block, paired_width))
                    if sel == 1:
                        abrupt = values[0, i, j]
                        difference = ((f[2] - f[0]) - (abrupt[2] - abrupt[0])).mean()
                        metrics.append(
                            metric(
                                "Exp 6 width contrast", f"{count} drops", "faded minus abrupt", amp, r.block, difference
                            )
                        )
                    metrics.append(
                        metric(
                            "Exp 6 branch change",
                            f"{count} drops",
                            kind,
                            amp,
                            r.block,
                            float(branch[i, j] != d["sweep_diff"][0]),
                        )
                    )
    pooled = np.mean([d["sweep_forecast"].mean(-1) for _, d in sweep], axis=0)
    values = pooled[1:].reshape(2, 6, 5, 3)
    for k, (ax, name) in enumerate(zip(axes.ravel(), ("q10", "q50", "q90", "Width"))):
        ax.set_title(f"{name} (°C)")
        for sel, style in enumerate(("--", "-")):
            for i, count in enumerate((1, 2, 4, 8, 12, 16)):
                data = np.vstack((pooled[0], values[sel, i]))
                ax.plot(
                    amplitudes,
                    data[:, k] if k < 3 else data[:, 2] - data[:, 0],
                    style,
                    c=colors[i],
                    label=str(count) if sel == 0 else None,
                )
    axes[0, 0].legend(title="Drop count", ncol=2, fontsize=8)
    fig.supxlabel("Inserted drop amplitude (°C)")
    fig.suptitle(f"4. Exp 6 sweep · dashed abrupt, solid faded (n={len(sweep)})")
    save_figure(fig, directory / "04_drop_sweep.png")


def upstream_panels(rows, out, directory, metrics):
    setups = ("pressure", "phase1", "wind", "wind_difference", "wind_change", "phase1_exp4")
    names = (
        "Pressure Δ3h",
        "Phase I upstream",
        "Wind pair",
        "Wind temperature gap",
        "Wind upstream Δ3h",
        "Phase I (1680 h)",
    )
    subset = [(r, d) for r, d in rows if "pressure_forecasts" in d]
    if subset:
        fig, axes = plt.subplots(2, 3, figsize=(16, 8), layout="constrained")
        colors = plt.cm.tab10.colors
        for k, (setup, name) in enumerate(zip(setups, names)):
            forecast = np.array([d[f"{setup}_forecasts"] for _, d in subset])
            truth = np.array([d["truth"] for _, d in subset])
            q50 = forecast[:, :3, 1]
            actual_drop = truth[:, 6] - np.min(truth[:, 6:13], axis=1)
            valid = actual_drop >= 2
            for s, kind in [(0, "temperature only"), (1, "observed lag"), (2, "shifted 24 h")]:
                effect = q50[:, s] - q50[:, 0]
                absolute = np.abs(q50[:, s] - truth)
                error = absolute - np.abs(q50[:, 0] - truth)
                drop = q50[:, s, 6] - np.min(q50[:, s, 6:13], axis=1)
                drop_base = q50[:, 0, 6] - np.min(q50[:, 0, 6:13], axis=1)
                capture = drop[valid] / actual_drop[valid] * 100
                x = k + 0.14 * (s - 1)
                style = (":", "-", "--")[s]
                if s > 0:
                    curve(axes[0, 0], effect, LEADS, name if s == 1 else None, color=colors[k], style=style)
                if s > 0 or k in (0, 5):
                    curve(axes[0, 1], absolute, LEADS, None, color=colors[k], style=style)
                if len(capture):
                    axes[0, 2].scatter(
                        np.full_like(capture, x),
                        capture,
                        color=colors[k],
                        marker=("_", "o", "x")[s],
                        s=17,
                        alpha=0.45,
                    )
                for j, (r, _) in enumerate(subset):
                    block = r.block
                    for lead, (change, delta) in enumerate(zip(effect[j], error[j]), 1):
                        metrics.extend(
                            [
                                metric("covariate forecast change", name, kind, lead, block, change),
                                metric("covariate absolute error change", name, kind, lead, block, delta),
                                metric("covariate absolute error", name, kind, lead, block, absolute[j, lead - 1]),
                            ]
                        )
                    if valid[j]:
                        metrics.append(
                            metric("covariate drop captured", name, kind, 0, block, drop[j] / actual_drop[j] * 100)
                        )
                        metrics.append(
                            metric(
                                "covariate drop captured change",
                                name,
                                kind,
                                0,
                                block,
                                (drop[j] - drop_base[j]) / actual_drop[j] * 100,
                            )
                        )
            timing_error = np.abs(q50[:, 1] - truth) - np.abs(q50[:, 2] - truth)
            captures = q50[:, 1:3, 6] - q50[:, 1:3, 6:13].min(axis=-1)
            for j, (r, _) in enumerate(subset):
                for h, difference in enumerate(timing_error[j], 1):
                    metrics.append(
                        metric(
                            "covariate timing error contrast", name, "observed minus shifted", h, r.block, difference
                        )
                    )
                if valid[j]:
                    difference = (captures[j, 0] - captures[j, 1]) / actual_drop[j] * 100
                    metrics.append(
                        metric(
                            "covariate timing capture contrast", name, "observed minus shifted", 0, r.block, difference
                        )
                    )
            # Signed derivative of a simultaneous one-standard-deviation increase
            # in the 24 newest observations of each feature.
            gradient = np.array([d[f"{setup}_grad"][..., -24:].sum(-1) for _, d in subset])
            finite = forecast[:, 4::2, 1] - forecast[:, 3::2, 1]
            for c in range(gradient.shape[2]):
                curve(axes[1, 0], gradient[:, :, c], LEADS, None, color=colors[k], style="-" if c == 0 else ":")
                curve(axes[1, 1], finite[:, c], LEADS, None, color=colors[k], style="-" if c == 0 else ":")
            for j, (r, _) in enumerate(subset):
                for c in range(gradient.shape[2]):
                    for h in range(24):
                        metrics.extend(
                            [
                                metric(
                                    "scaled covariate gradient",
                                    name,
                                    f"feature {c + 1}",
                                    h + 1,
                                    r.block,
                                    float(gradient[j, h, c]),
                                ),
                                metric(
                                    "covariate finite response",
                                    name,
                                    f"feature {c + 1}",
                                    h + 1,
                                    r.block,
                                    float(finite[j, c, h]),
                                ),
                            ]
                        )
        titles = (
            "q50 change vs temperature alone (°C)",
            "Mean absolute error (°C)",
            "Observed drop captured (%)",
            "Scaled covariate gradient (°C)",
            "Centered finite response (°C)",
        )
        for i, (ax, title) in enumerate(zip(axes.ravel(), titles)):
            ax.set_title(title)
            ax.axhline(0, color=".65", lw=0.7)
            if i != 2:
                ax.set_xlabel("Forecast lead (hours)")
        axes[0, 2].set_xticks(range(len(names)), names, rotation=25, ha="right", fontsize=8)
        axes[1, 2].axis("off")
        axes[1, 2].legend(
            *axes[0, 0].get_legend_handles_labels(), loc="center", title="Solid actual, dashed shifted, dotted T2M"
        )
        fig.suptitle(f"5. Upstream and pressure information (n={len(subset)})")
        save_figure(fig, directory / "05_upstream.png")

    path = out / "synthetic_flags.npz"
    if path.exists():
        with np.load(path) as data:
            q50 = data["forecast"][:, :, 1]
            counts = data["counts"]
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
        response = q50[:, 1] - q50[:, 0]
        for count, delta in zip(counts, response):
            axes[0].plot(LEADS, delta, label=str(count))
        axes[0].axvline(13, color=".5", ls="--")
        axes[0].set(xlabel="Forecast lead (hours)", ylabel="Flag on minus flag off (°C)")
        axes[0].legend(title="Prior pairs", ncol=2, fontsize=8)
        axes[1].plot(counts, response[:, 12], "o-", label="+13 h")
        axes[1].plot(counts, response[:, -1], "s-", label="+24 h")
        axes[1].set(xlabel="Previous flag–drop pairs", ylabel="Flag on minus flag off (°C)")
        axes[1].legend()
        fig.suptitle("5. Synthetic warning diagnostic · front begins at +13 h")
        save_figure(fig, directory / "05_synthetic_warning.png")


def skill_panel(rows, out, directory, metrics):
    source = pd.read_csv(out / "phase1_skill_by_block.csv")
    source = pd.concat([source, source.assign(cohort="all")], ignore_index=True)
    rng = np.random.default_rng(0)
    skill_rows = []
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, layout="constrained")
    for cohort in ("all", *COHORTS):
        subset = source[source.cohort == cohort]
        block = subset.groupby(["block", "lead"])[["model_abs_sum", "baseline_abs_sum", "n"]].sum()
        model, reference, counts = [block[col].unstack("lead", fill_value=0).to_numpy() for col in block.columns]
        total_n = counts.sum(0)
        mae = model.sum(0) / total_n
        base = reference.sum(0) / total_n
        skill = (1 - mae / base) * 100
        selected = rng.integers(len(model), size=(1000, len(model)))
        draws = (1 - model[selected].sum(1) / reference[selected].sum(1)) * 100
        bounds = np.quantile(draws, [0.025, 0.975], axis=0)
        (line,) = axes[0, 0].plot(LEADS, mae, label=cohort)
        axes[0, 0].plot(LEADS, base, "--", color=line.get_color())
        axes[0, 1].plot(LEADS, skill, color=line.get_color())
        axes[0, 1].fill_between(LEADS, *bounds, color=line.get_color(), alpha=0.10)
        skill_rows.append(
            pd.DataFrame(
                {
                    "cohort": cohort,
                    "lead": LEADS,
                    "n": total_n,
                    "blocks": len(model),
                    "mae": mae,
                    "yesterday_mae": base,
                    "skill_percent": skill,
                    "low": bounds[0],
                    "high": bounds[1],
                }
            )
        )
        subset = [(r, d) for r, d in rows if r.skill_case and (r.cohort == cohort or cohort == "all")]
        if subset:
            mass = [np.nanmean(np.abs(d["median_grad"]), axis=-1) for _, d in subset]
            newest = [ratio(profile(d["median_grad"], 32)) for _, d in subset]
            curve(axes[1, 0], mass, LEADS, f"{cohort} (n={len(subset)})", color=line.get_color())
            curve(axes[1, 1], newest, LEADS, None, color=line.get_color())
            for (r, _), raw, edge in zip(subset, mass, newest):
                for lead, (magnitude, edge_ratio) in enumerate(zip(raw, edge), 1):
                    for name, value in [("lead gradient magnitude", magnitude), ("lead position ratio", edge_ratio)]:
                        metrics.append(metric(name, cohort, "gradient", lead, r.block, value))
    pd.concat(skill_rows).to_csv(directory / "phase1_lead_skill.csv", index=False)
    axes[0, 0].set_title("Saved Phase I MAE (°C) · dashed same hour yesterday")
    axes[0, 1].set_title("Skill vs same hour yesterday (%)")
    axes[0, 1].axhline(0, color=".6", lw=0.7)
    axes[1, 0].set_title("Pilot mean absolute q50 derivative")
    axes[1, 1].set_title("Pilot newest two / mean slot · omit newest patch")
    axes[0, 0].legend(fontsize=8)
    if axes[1, 0].lines:
        axes[1, 0].legend(fontsize=8)
    fig.supxlabel("Forecast lead (hours)")
    fig.suptitle("Saved forecast skill and Phase II sensitivity")
    save_figure(fig, directory / "06_skill.png")


def table(frame, cols):
    rows = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in frame[cols].itertuples(index=False, name=None):
        rows.append(
            "| "
            + " | ".join(
                f"{x:.3f}" if isinstance(x, float) and np.isfinite(x) else "—" if pd.isna(x) else str(x) for x in r
            )
            + " |"
        )
    return "\n".join(rows)


def branch_log(rows):
    log = []
    for r, data in rows:
        for key, values in data.items():
            if not key.endswith("_diff") or key == "base_diff":
                continue
            name = key.removesuffix("_diff")
            paired = bool(data["base_diff"])
            if name == "sweep" or f"{name}_inputs" in data:
                paired, values = bool(values[0]), values[1:]
            values = np.asarray(values)
            log.append(
                {
                    "case_id": r.case_id,
                    "block": r.block,
                    "setup": name,
                    "base_diff": paired,
                    "pairs": values.size,
                    "branch_changes": int((values != paired).sum()),
                }
            )
    return pd.DataFrame(log, columns=["case_id", "block", "setup", "base_diff", "pairs", "branch_changes"])


def report(out, pilot_only, *, directory=None):
    cases = pd.read_csv(out / "cases.csv")
    blocks = pd.read_csv(out / "analysis_blocks.csv").set_index("o").analysis_block
    cases["selection_block"] = cases.block
    cases["block"] = cases.o.map(blocks)
    if pilot_only:
        cases = cases[cases.pilot_order.notna()].sort_values("pilot_order")
    design = json.loads((out / "design.json").read_text())
    rows = records(cases, out, design["manifest_id"])
    if directory is None:
        directory = out / ("pilot_report" if pilot_only else "report")
    directory.mkdir(parents=True, exist_ok=True)
    data_link = os.path.relpath(out.resolve(), directory.resolve())
    metrics = []
    patch_panels(rows, directory, metrics)
    front_panels(rows, directory, metrics)
    interval_panels(rows, directory, metrics)
    upstream_panels(rows, out, directory, metrics)
    skill_panel(rows, out, directory, metrics)
    frame = pd.DataFrame(metrics)
    blocks, estimates = clustered(
        frame.dropna(subset=["value"]) if len(frame) else frame, ["panel", "group", "setup", "lead"]
    )
    blocks.to_csv(directory / "by_event_or_block.csv", index=False)
    estimates.to_csv(directory / "estimates.csv", index=False)
    branch_log(rows).to_csv(directory / "branch_changes.csv", index=False)
    completed = cases[cases.case_id.isin({r.case_id for r, _ in rows})]
    completed.to_csv(directory / "reported_cases.csv", index=False)
    lines = [
        "# Phase II TiRex-2 weather figures",
        "",
        f"**{len(rows)} of {len(cases)} cases available.** "
        + (
            "Eight-case runtime pilot."
            if pilot_only
            else "Full manifest analysis."
            if len(rows) == len(cases)
            else "Partial full-manifest analysis."
        ),
        "",
        f"Exp 10 cases use {design['exp10_source']}. Exp 6 drop profile uses the {design['exp6_shape_source']}.",
        "",
        (
            "The forecast origin is the first forecast hour. The preceding observation is lag 1. "
            "Phase I bins use observed lead +24 minus lag 1. Curves pool cases. "
            "The estimates table weights contiguous forecast blocks equally and includes 95% block-bootstrap intervals "
            "where at least three blocks are available. A block contains all stations at an origin and contains any starts with overlapping verification windows. The Phase I skill panel weights paired forecasts equally and resamples whole blocks."
        ),
        "",
        "## Available cases",
        "",
    ]
    counts = []
    for name, subset in [
        ("Exp 10 ordinary", completed[completed.exp10.eq("ordinary")]),
        ("Exp 10 pre-front", completed[completed.exp10.eq("pre-front")]),
        *[(cohort, completed[completed.skill_case & completed.cohort.eq(cohort)]) for cohort in COHORTS],
        ("Pulse and embedding", completed[completed.pulse]),
        ("Local front alignment", completed[completed.aligned]),
        (
            "Paired level and slope",
            completed[completed.case_id.isin([r.case_id for r, d in rows if "level_slope_forecast" in d])],
        ),
        ("Exp 6 sweep", completed[completed.sweep]),
        ("Upstream covariates", completed[completed.upstream]),
    ]:
        counts.append({"Cohort": name, "Cases": len(subset), "Blocks": subset.block.nunique()})
    lines.extend([table(pd.DataFrame(counts), ["Cohort", "Cases", "Blocks"]), ""])
    timing_path = out / "pilot_timing.json"
    if timing_path.exists():
        timing = json.loads(timing_path.read_text())
        times = [r["seconds"] for r in timing["cases"]]
        rss = max(r["max_rss_mib"] for r in timing["cases"])
        lines.extend(
            [
                (
                    f"Pilot total case time was {sum(times):.1f} s. Case times ranged from {min(times):.1f} to "
                    f"{max(times):.1f} s and peak process RSS was {rss:.0f} MiB."
                ),
                "",
            ]
        )
    if len(estimates):
        patch = estimates[(estimates.panel == "patch ratio") & estimates.lead.isin([24, 32])]
        if len(patch):
            lines.extend(
                [
                    "## Newest-two sensitivity ratio",
                    "",
                    table(patch, ["group", "setup", "lead", "n", "blocks", "estimate", "low", "high"]),
                    "",
                    (
                        "The lead column in this table gives the number of excluded input hours. "
                        "NaN masking is measured in °C, while gradients and centered finite differences measure the "
                        "forecast response per degree of input change. The ratio is dimensionless."
                    ),
                    "",
                ]
            )
        for section, panel_names, lead in [
            ("Newest-two ratio in embedding output changes", ["embedding newest-two ratio"], 0),
            ("Change by cohort at +24 h", ["change"], 24),
            ("Level and swing responses", ["forecast level response", "forecast swing response"], 24),
            (
                "Interval diagnostics at +12 h by issuance phase",
                ["width", "median bias", "below", "inside", "above"],
                12,
            ),
        ]:
            panel = estimates[estimates.panel.isin(panel_names) & estimates.lead.eq(lead)]
            if len(panel):
                lines.extend(
                    [
                        f"## {section}",
                        "",
                        table(panel, ["panel", "group", "setup", "n", "blocks", "estimate", "low", "high"]),
                        "",
                    ]
                )
    lines.extend(["## Figures and estimates", ""])
    titles = {
        "01_patch_heatmaps": "Signed and folded temperature sensitivity",
        "02_patch_controls": "Gradient, masking and finite-difference controls",
        "02_patch_strata": "Gradient profiles by season and region",
        "02_pulse_embedding": "Cooling pulse and embedding responses",
        "03_front_alignment": "Forecasts aligned to local passage",
        "03_change_cohorts": "Predicted and observed changes",
        "03_level_slope": "Level and slope interventions",
        "03_internal_gates": "sLSTM gate saliency and memory flow",
        "03_internal_heads": "Signed mLSTM coefficients by head",
        "04_coverage": "Lead-matched coverage, width and bias",
        "04_coverage_saliency": "Covered and missed case saliency",
        "04_drop_sweep": "Exp 6 abrupt and faded drop sweeps",
        "05_upstream": "Pressure, upstream and shifted controls",
        "05_synthetic_warning": "Synthetic warning flag response",
        "06_skill": "Phase I baseline skill and Phase II sensitivity",
    }
    for name, title in titles.items():
        if name == "03_front_alignment" and not completed.aligned.any():
            continue
        if (directory / f"{name}.png").exists():
            lines.append(f"- [{title}]({name}.png)")
    lines.extend(
        [
            "- [Block-level estimates](by_event_or_block.csv)",
            "- [Bootstrap estimates](estimates.csv)",
            "- [Preprocessing branch changes](branch_changes.csv)",
            "- [Original Phase I lead skill](phase1_lead_skill.csv)",
            "- [Cases included](reported_cases.csv)",
            f"- [Case manifest]({data_link}/cases.csv)",
            f"- [Real-weather preflight]({data_link}/preflight.json)",
            f"- [Signed arrays and intervention forecasts]({data_link}/arrays/)",
            "",
        ]
    )
    (directory / "REPORT.md").write_text("\n".join(lines))
    print(f"{len(rows)}/{len(cases)} cases reported in {directory}")
