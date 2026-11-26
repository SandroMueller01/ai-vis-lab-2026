"""Join Phase I forecasts to INCA and select reproducible Phase II cases."""

import base64
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CONTEXT, HORIZON, LONG = 672, 24, 1680
OFFSETS = (-6, 0, 3, 6, 12)


def group_change(change):
    return np.select(
        [change < -5, (change >= -2) & (change < 2), change >= 5],
        ["cooling", "stable", "warming"],
        default="intermediate",
    )


def timestamps(values):
    numeric = np.asarray(values)
    if np.issubdtype(numeric.dtype, np.integer):
        unit = "ns" if abs(numeric[0]) > 10**17 else "us"
        return pd.DatetimeIndex(pd.to_datetime(numeric, unit=unit, utc=True))
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True, format="mixed"))


def spreads(frame, count, rng, block="block"):
    """Round-robin across shuffled events or calendar blocks."""
    if frame.empty:
        return frame
    shuffled = frame.iloc[rng.permutation(len(frame))].copy()
    return shuffled.loc[shuffled.groupby(block, sort=False).cumcount().sort_values(kind="stable").index[:count]]


class Weather:
    def __init__(self, directory, forecasts):
        self.directory = directory
        self.forecasts = forecasts
        self.cache = None
        data = pd.read_parquet(directory / "grid_long.parquet", columns=["point_id", "time", "T2M"])
        self.raw = data.pivot(index="time", columns="point_id", values="T2M")
        self.raw.index = timestamps(self.raw.index)
        self.times = self.raw.index
        if not np.all(np.diff(self.times.as_unit("ns").asi8) == 3_600_000_000_000):
            raise ValueError("INCA timestamps must be a continuous hourly grid")
        self.temperature = self.raw.interpolate(limit=3, limit_area="inside").to_numpy(np.float32)
        self.raw = self.raw.to_numpy(np.float32)
        self.points = pd.read_csv(directory / "points_with_labels.csv").set_index("point_id")
        self.point_ids = np.sort(data.point_id.unique())
        self.points = self.points.loc[self.point_ids]
        self.columns = {p: i for i, p in enumerate(self.point_ids)}
        if not all((directory / name).exists() for name in ("events.parquet", "fronts.csv")):
            subprocess.run(
                [sys.executable, str(ROOT / "data_acquisition/events/build_events.py"), "--data", str(directory)],
                check=True,
            )
        events = pd.read_parquet(directory / "events.parquet")
        events = events[events.kind == "cold_front"].copy()
        events["onset"] = timestamps(events.time)
        fronts = pd.read_csv(directory / "fronts.csv")
        self.peaks = timestamps(fronts.loc[fronts.cold_front, "peak_time"])
        # The builder accepts onsets in [peak-12h, peak+12h). Keep the first
        # local onset per station/system, as in the Phase I front analysis.
        self.local = pd.concat(
            [
                events.loc[
                    (events.onset >= peak - pd.Timedelta(hours=12)) & (events.onset < peak + pd.Timedelta(hours=12))
                ]
                .groupby("point_id", as_index=False)
                .onset.min()
                .assign(event=str(peak))
                for peak in self.peaks
            ],
            ignore_index=True,
        )
        self.local["passage"] = self.times.get_indexer(self.local.onset)

    def history(self, row, length=CONTEXT):
        return self.temperature[row.o - length : row.o, self.columns[row.point_id]].copy()

    def truth(self, row):
        return self.raw[row.o : row.o + HORIZON, self.columns[row.point_id]]

    def annotate(self, rows):
        rows = rows.copy()
        rows["origin"] = self.times[rows.o]
        # Lead 1 is the saved Phase I origin (the first forecast hour).
        p = rows.point_id.map(self.columns).to_numpy()
        o = rows.o.to_numpy()
        change = self.raw[o + 23, p] - self.raw[o - 1, p]
        rows["change24"] = change
        rows["cohort"] = group_change(change)
        rows["season"] = np.array(["DJF", "MAM", "JJA", "SON"])[(rows.origin.dt.month % 12) // 3]
        rows["utc_hour"] = rows.origin.dt.hour
        # Broad longitude regions keep the regional comparison interpretable.
        rows["region"] = pd.cut(
            self.points.loc[rows.point_id, "lon"].to_numpy(),
            [-np.inf, 13, 15, np.inf],
            labels=["west", "central", "east"],
        )
        rows["variability"] = np.nanstd(self.temperature[o[:, None] - np.arange(1, 25), p[:, None]], axis=1)
        rows["event"] = ""
        rows["passage"] = -1
        rows["offset"] = np.nan
        # Link a start to the closest local passage within 36 hours.
        for point, indices in rows.groupby("point_id").groups.items():
            local = self.local[self.local.point_id == point]
            if local.empty:
                continue
            delta = rows.loc[indices, "o"].to_numpy()[:, None] - local.passage.to_numpy()
            closest = np.abs(delta).argmin(axis=1)
            offset = delta[np.arange(len(closest)), closest]
            near = np.abs(offset) <= 36
            indices = indices[near]
            matched = local.iloc[closest[near]]
            rows.loc[indices, "event"] = matched.event.to_numpy()
            rows.loc[indices, "passage"] = matched.passage.to_numpy()
            rows.loc[indices, "offset"] = offset[near]
        rows["block"] = rows.origin.dt.tz_localize(None).dt.to_period("W-SUN").astype(str)
        rows["block"] = rows.event.where(rows.event.ne(""), rows.block)
        return rows

    def saved(self):
        with np.load(self.forecasts) as data:
            self.cache = data["preds"]
            starts = timestamps(data["times"])[data["origin_idx"]]
            origins = self.times.get_indexer(starts)
            points = data["pids"]
            if (origins < CONTEXT).any() or not set(points).issubset(self.columns):
                raise ValueError("Phase I origins or point IDs do not match the weather grid")
            n, m = len(origins), len(points)
            candidates = pd.DataFrame(
                {
                    "o": np.repeat(origins, m),
                    "tag": np.repeat(data["tags"], m),
                    "point_id": np.tile(points, n),
                    "saved_run": np.repeat(np.arange(n), m),
                    "saved_point": np.tile(np.arange(m), n),
                }
            )
        # A start can be scheduled both by the grid and by a front tag.
        return self.annotate(candidates).drop_duplicates(["point_id", "o"])

    def near_front(self, offsets, length):
        cases = pd.concat([self.local.assign(o=self.local.passage + offset) for offset in offsets])
        cases = cases.loc[cases.o.between(length, len(self.times) - HORIZON), ["point_id", "o"]]
        return self.annotate(cases.drop_duplicates().reset_index(drop=True))

    def drop_shape(self, results):
        original = results / "exp6_weird_context.npz"
        composite = results / "exp5_after_front.npz"
        if original.exists():
            with np.load(original) as data:
                if "shape" in data:
                    return data["shape"], "original Exp 6 array"
        if composite.exists():
            with np.load(composite) as data:
                hours, med = data["comp_rel"], data["comp_T2M_median"]
                shape = med[(hours >= 0) & (hours <= 48)] - med[(hours >= -6) & (hours < 0)].mean()
                return (shape / -shape.min()).astype(np.float32), "original Exp 5 composite"
        published = (
            ROOT / "phase1-model-behavior/pair-1/experiments/figures/exp5" / "exp5_average_front_all_variables.html"
        )
        if published.exists():
            # Plotly stores the temperature median as the second trace (after
            # its interquartile band). Decode the checked-in data without JS.
            arguments = published.read_text().split("Plotly.newPlot(", 1)[1].lstrip()
            decoder = json.JSONDecoder()
            _, end = decoder.raw_decode(arguments)
            traces, _ = decoder.raw_decode(arguments[end:].lstrip().removeprefix(",").lstrip())
            hours, med = (plotly_array(traces[1][axis]) for axis in ("x", "y"))
            if not np.array_equal(hours, np.arange(-48, 97)) or "temperature" not in traces[1]["hovertemplate"]:
                raise ValueError("Unexpected Phase I composite figure")
            shape = med[(hours >= 0) & (hours <= 48)] - med[(hours >= -6) & (hours < 0)].mean()
            return (shape / -shape.min()).astype(np.float32), "anomaly composite published in Phase I Exp 5"
        # Rebuild an observed composite with the same support and normalization.
        rows = self.local[self.local.passage.between(6, len(self.times) - 49)]
        indices = rows.passage.to_numpy()[:, None] + np.arange(-6, 49)
        columns = rows.point_id.map(self.columns).to_numpy()
        med = np.nanmedian(self.temperature[indices, columns[:, None]], axis=0)
        shape = med[6:] - med[:6].mean()
        return (shape / -shape.min()).astype(np.float32), "rebuilt local-passage composite"


def plotly_array(values):
    if isinstance(values, dict):
        return np.frombuffer(base64.b64decode(values["bdata"]), dtype=values["dtype"])
    return np.asarray(values)


def original_rows(weather, path):
    with np.load(path) as data:
        rows = pd.DataFrame({"point_id": data["point_id"], "o": weather.times.get_indexer(timestamps(data["start"]))})
        if (rows.o < CONTEXT).any() or not set(rows.point_id).issubset(weather.columns):
            raise ValueError(f"Invalid original case IDs in {path}")
        if "group" in data:
            rows["exp10"] = pd.Series(data["group"]).map({"normal day": "ordinary", "cold front": "pre-front"})
    return weather.annotate(rows)


def match_stable(stable, changes, count, rng):
    available = stable.loc[rng.permutation(stable.index)].copy()
    matches = []
    for row in changes.itertuples():
        same = available[(available.season == row.season) & (available.utc_hour == row.utc_hour)]
        same = same[same.point_id == row.point_id]
        if same.empty:
            continue
        idx = (same.variability - row.variability).abs().idxmin()
        matches.append(available.loc[idx].to_dict())
        matches[-1].update(matched_point=row.point_id, matched_origin=str(row.origin))
        available = available.drop(idx)
        if len(matches) >= count:
            break
    return pd.DataFrame(matches)


def manifest(weather, candidates, results, seed):
    rng = np.random.default_rng(seed)
    pre = weather.near_front([-6], CONTEXT)
    pre = pre.loc[[weather.truth(r)[6] - np.min(weather.truth(r)[6:13]) >= 2 for r in pre.itertuples()]]
    eligible10 = results / "exp10_occlusion_40x2.npz"
    e2, e3 = (results / name for name in ("exp2_forecasts_50x48.npz", "exp3_forecasts_30perfront.npz"))
    if eligible10.exists():
        exp10 = original_rows(weather, eligible10)
        source = "original Exp 10 case IDs"
    elif e2.exists() and e3.exists():
        original_rng = np.random.default_rng(0)
        ordinary = original_rows(weather, e2)
        front = original_rows(weather, e3)
        with np.load(e3) as data:
            y = data["truth"]
            eligible = np.flatnonzero(y[:, 6] - y[:, 6:13].min(axis=1) >= 2)
        exp10 = pd.concat(
            [
                ordinary.iloc[original_rng.choice(len(ordinary), 40, replace=False)].assign(exp10="ordinary"),
                front.iloc[original_rng.choice(eligible, 40, replace=False)].assign(exp10="pre-front"),
            ]
        )
        source = "Exp 10 IDs reconstructed from original Exp 2 and Exp 3 files"
    else:
        ordinary = candidates[candidates.tag.eq("grid") & candidates.event.eq("") & candidates.change24.notna()]
        exp10 = pd.concat(
            [spreads(ordinary, 40, rng).assign(exp10="ordinary"), spreads(pre, 40, rng).assign(exp10="pre-front")]
        )
        source = "a seeded replacement. Phase I reported a masking ratio of 2.0 with 97% of ordinary cases above one"
    exp10["pulse"] = False
    exp10 = exp10.reset_index(drop=True)
    for _, group in exp10.groupby("exp10"):
        exp10.loc[spreads(group, 12, rng).index, "pulse"] = True
    selected = [
        spreads(candidates[candidates.cohort == cohort], 48, rng).assign(skill_case=True)
        for cohort in ("cooling", "warming")
    ]
    interleaved = pd.concat([group.assign(order=np.arange(len(group))) for group in selected])
    stable = candidates[(candidates.cohort == "stable") & candidates.event.eq("")]
    selected.append(
        match_stable(stable, interleaved.sort_values("order", kind="stable"), 48, rng).assign(skill_case=True)
    )
    fronts = weather.near_front(OFFSETS, CONTEXT)
    front_keys = spreads(fronts[fronts.offset.eq(-6) & fronts.passage.ge(CONTEXT + 6)], 24, rng)
    fronts = fronts.merge(front_keys[["point_id", "event"]], on=["point_id", "event"]).assign(aligned=True)
    files6 = results / "exp6_weird_context.npz"
    if files6.exists():
        drop_cases = original_rows(weather, files6)
    elif e3.exists():
        drop_cases = original_rows(weather, e3)
        with np.load(e3) as data:
            y = data["truth"]
            drop_cases = drop_cases.loc[y[:, 6] - y[:, 6:13].min(axis=1) >= 2]
    else:
        drop_cases = spreads(pre[pre.o.ge(LONG)], 24, rng)
    drop_cases = drop_cases[drop_cases.o.ge(LONG)].assign(sweep=True)
    upstream = spreads(pre[pre.o.ge(LONG + 27)], 40, rng).assign(upstream=True)
    merged = pd.concat([exp10, *selected, fronts, drop_cases, upstream], ignore_index=True)
    flags = ["pulse", "skill_case", "aligned", "sweep", "upstream"]
    merged[flags] = merged[flags].eq(True)
    for name in ["matched_point", "matched_origin"]:
        if name not in merged:
            merged[name] = np.nan
    aggregations = {name: "first" for name in merged.columns.difference(["point_id", "o", *flags])}
    aggregations.update(dict.fromkeys(flags, "max"))
    merged = merged.groupby(["point_id", "o"], sort=False, as_index=False).agg(aggregations)
    merged["case_id"] = merged.point_id.astype(str) + "_" + merged.o.astype(str)
    # The eight cases cover both Exp 10 groups, all three change cohorts and all intervention families.
    pilot = []
    for mask, count in [
        (merged.exp10.eq("ordinary") & merged.pulse, 2),
        (merged.exp10.eq("pre-front") & merged.pulse, 2),
        (merged.skill_case & merged.cohort.eq("stable"), 1),
        (merged.skill_case & merged.cohort.eq("warming"), 1),
        (merged.upstream, 1),
        (merged.sweep, 1),
    ]:
        pilot.extend(spreads(merged[mask & ~merged.case_id.isin(pilot)], count, rng).case_id)
    merged["pilot_order"] = merged.case_id.map({case: i for i, case in enumerate(pilot)})
    return merged, source
