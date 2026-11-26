#!/usr/bin/env python3
"""Prepare, run, and report the Phase II TiRex-2 weather experiments."""

import argparse
import hashlib
import json
import os
import resource
import tempfile
from pathlib import Path
from time import perf_counter

# Some layers in the pinned source are decorated with torch.compile independently
# of the load_model option. Eager execution keeps their hooks and kernels visible.
os.environ["TORCHDYNAMO_DISABLE"] = "1"

import numpy as np
import pandas as pd
from pilot_cases import ROOT, Weather, manifest

REVISION = "30788a311699acba7e6393ad9700ea7b7cb9bb2d"
DEFAULT_DATA = ROOT / "data/austria_15km"
DEFAULT_OUTPUT = ROOT / "data/tirex2-phase2"
HERE = Path(__file__).resolve().parent


def atomic(path, writer):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
        temporary = Path(out.name)
        try:
            writer(out)
            out.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def save(path, **arrays):
    atomic(path, lambda out: np.savez_compressed(out, **arrays))


def write_json(path, data):
    atomic(path, lambda out: out.write((json.dumps(data, indent=2) + "\n").encode()))


def args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "preflight", "pilot", "run", "report"])
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--forecasts", type=Path)
    parser.add_argument("--phase1-results", type=Path, default=ROOT / "data/notebooks/results")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path.home() / (f".cache/huggingface/hub/models--NX-AI--TiRex-2/snapshots/{REVISION}"),
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--pilot-only", action="store_true", help="Report only the eight pilot cases")
    parser.add_argument("--report-dir", type=Path, help="Directory for the report and figures")
    a = parser.parse_args()
    if not 0 <= a.shard_index < a.shard_count or min(a.threads, a.batch_size) < 1:
        parser.error("require positive threads and batch size, and 0 <= shard index < shard count")
    if a.report_dir is not None and a.command != "report":
        parser.error("--report-dir requires the report command")
    return a


def main():
    a = args()
    out = a.out
    manifest_path = out / "cases.csv"
    out.mkdir(parents=True, exist_ok=True)
    if a.command == "report":
        from pilot_report import report

        report(out, a.pilot_only, directory=a.report_dir)
        return

    a.data = a.data.resolve()
    weather = Weather(a.data, (a.forecasts or a.data / "tirex2_forecasts.npz").resolve())
    if a.command == "prepare":
        from pilot_report import baseline

        candidates = weather.saved()
        cases, source = manifest(weather, candidates, a.phase1_results, a.seed)
        shape, shape_source = weather.drop_shape(a.phase1_results)
        join = cases[["case_id", "point_id", "o", "origin"]].merge(
            candidates[["point_id", "o", "saved_run", "saved_point", "tag"]],
            on=["point_id", "o"],
            how="left",
            validate="1:1",
        )
        join.to_csv(out / "phase1_case_join.csv", index=False)
        content = cases.to_csv(index=False).encode()
        manifest_id = hashlib.sha256(content + shape.tobytes()).hexdigest()
        atomic(manifest_path, lambda f: f.write(content))
        save(out / "design.npz", drop_shape=shape)
        write_json(
            out / "design.json",
            {
                "manifest_id": manifest_id,
                "seed": a.seed,
                "exp10_source": source,
                "exp6_shape_source": shape_source,
                "manifest_cases": len(cases),
                "observations": str(a.data / "grid_long.parquet"),
                "phase1_forecasts": str(weather.forecasts),
            },
        )
        # Every station at an origin, and every chain of overlapping forecast
        # windows, belongs to the same resampling unit.
        origins = np.union1d(candidates.o, cases.o)
        starts = origins[
            np.maximum.accumulate(np.where(np.r_[True, np.diff(origins) >= 24], np.arange(len(origins)), 0))
        ]
        blocks = pd.Series(weather.times[starts].strftime("%Y-%m-%d %H:%M UTC").to_numpy(), index=origins)
        blocks.rename_axis("o").rename("analysis_block").to_csv(out / "analysis_blocks.csv")
        candidates["block"] = candidates.o.map(blocks)
        baseline(weather, candidates).to_csv(out / "phase1_skill_by_block.csv", index=False)
        print(f"{len(cases)} manifest cases, {len(candidates)} unique Phase I forecasts. {source}", flush=True)
        return

    import torch
    from pilot_experiments import Covariates, Model, run_case, synthetic_flags

    if torch.__version__.split("+")[0] != "2.9.1":
        raise RuntimeError("Use the separate CPU PyTorch 2.9.1 environment in README.md")
    torch.set_num_threads(a.threads)
    cases = pd.read_csv(manifest_path)
    design = json.loads((out / "design.json").read_text())
    manifest_id = design["manifest_id"]
    with np.load(out / "design.npz") as data:
        shape = data["drop_shape"]
    if hashlib.sha256(manifest_path.read_bytes() + shape.tobytes()).hexdigest() != manifest_id:
        raise ValueError("The case manifest and saved design differ. Run prepare again.")
    if str(a.data / "grid_long.parquet") != design["observations"]:
        raise ValueError("Use the same weather input as prepare")
    pilot = cases[cases.pilot_order.notna()].sort_values("pilot_order")
    model = Model(a.checkpoint, a.batch_size)
    receiver, starts = model.mapping()
    start = perf_counter()
    if a.command == "preflight":
        row = next(pilot.itertuples())
        verification = model.gradients(weather.history(row), trace=True, verify=True)
        save(out / "preflight_arrays.npz", token_starts=starts, receiver=receiver, **verification)
        write_json(
            out / "preflight.json",
            {
                **model.settings(),
                "manifest_id": manifest_id,
                "case_id": row.case_id,
                "final_context_receiver": receiver,
                "leads_using_receiver": list(range(1, 25)),
                "parity_max_abs_c": verification["parity_max_abs_c"],
                "realized_diff": verification["diff"],
                "checks": [
                    "public forecast parity",
                    "finite observed gradients",
                    "sLSTM hidden reconstruction",
                    "mLSTM kernel reconstruction",
                    "lag and receiver mapping",
                ],
                "seconds": perf_counter() - start,
                "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            },
        )
        save(out / "synthetic_flags.npz", **synthetic_flags(model))
        print("Real-weather preflight passed", flush=True)
        return

    preflight = json.loads((out / "preflight.json").read_text())
    if preflight["manifest_id"] != manifest_id:
        raise ValueError("Run preflight on the current manifest before running cases")
    if a.command == "run":
        pilot_log = json.loads((out / "pilot_timing.json").read_text())
        if pilot_log["manifest_id"] != manifest_id or len(pilot_log["cases"]) != 8:
            raise ValueError("Complete the eight-case pilot on the current manifest before running full shards")
    selected = (
        pilot if a.command == "pilot" else cases.sort_values(["aligned", "pulse"], ascending=False, kind="stable")
    )
    selected = selected.iloc[a.shard_index :: a.shard_count]
    archive = out / "arrays"
    covariates = Covariates(weather) if selected.upstream.any() else None
    for row in selected.itertuples():
        path = archive / f"{row.case_id}.npz"
        if path.exists():
            with np.load(path) as data:
                if data["manifest_id"].item() != manifest_id:
                    raise ValueError(f"{path} belongs to a different manifest. Use a new output directory.")
            continue
        started = perf_counter()
        print(f"Starting {row.case_id}", flush=True)
        result = run_case(model, weather, row, receiver, shape, covariates, pilot=a.command == "pilot")
        seconds = perf_counter() - started
        mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        save(
            path,
            manifest_id=manifest_id,
            token_starts=starts,
            receiver=receiver,
            seconds=seconds,
            max_rss_mib=mem,
            **result,
        )
        print(f"{row.case_id}: {seconds:.1f} s, peak process RSS {mem:.0f} MiB", flush=True)
    if a.command == "pilot" and all((archive / f"{case_id}.npz").exists() for case_id in pilot.case_id):
        timings = []
        for case_id in pilot.case_id:
            with np.load(archive / f"{case_id}.npz") as data:
                if data["manifest_id"].item() != manifest_id:
                    raise ValueError(f"Stale pilot case {case_id}")
                timings.append(
                    {"case_id": case_id, "seconds": float(data["seconds"]), "max_rss_mib": float(data["max_rss_mib"])}
                )
        write_json(out / "pilot_timing.json", {"manifest_id": manifest_id, **model.settings(), "cases": timings})


if __name__ == "__main__":
    main()
