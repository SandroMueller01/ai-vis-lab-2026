# Phase II TiRex-2 visualization pilot

The runner joins the Austria 15 km INCA grid to saved Phase I forecasts and writes a case manifest, signed arrays, intervention forecasts, event/block estimates, and figures. See the [internal maps guide](TiRex2_Internal_Maps_Guide.md) for the interpretation and validation of the trace helpers.

## Reproduce the run

Run from the repository root. Use Python 3.11 or 3.12 and keep the existing Phase I environment for its notebooks. The Phase II runner checks the TiRex-2 source commit and the SHA-256 of the checkpoint files.

```bash
uv venv --python 3.11 /tmp/tirex-phase2-cpu
uv pip install --python /tmp/tirex-phase2-cpu/bin/python \
  --index https://download.pytorch.org/whl/cpu 'torch==2.9.1+cpu'
uv pip install --python /tmp/tirex-phase2-cpu/bin/python \
  'tirex-2 @ git+https://github.com/NX-AI/tirex-2.git@9e9d19a1767845e986a084924ddb64eb1aa1c49a' \
  'numpy==2.4.6' 'pandas==3.1.1' 'pyarrow==26.0.1' 'matplotlib==3.11.2'

python=/tmp/tirex-phase2-cpu/bin/python
pair=phase2-model-internals/pair-2
out=data/tirex2-phase2
revision=30788a311699acba7e6393ad9700ea7b7cb9bb2d
checkpoint="${HF_HUB_CACHE:-${HF_HOME:-$HOME/.cache/huggingface}/hub}/models--NX-AI--TiRex-2/snapshots/$revision"
export MPLCONFIGDIR=/tmp/tirex-phase2-mpl

TORCHDYNAMO_DISABLE=1 "$python" "$pair/tirex2_internal_maps.py" \
  --checkpoint "$checkpoint" --out "$out/synthetic"
"$python" "$pair/run_phase2_pilot.py" prepare --out "$out"
"$python" "$pair/run_phase2_pilot.py" preflight --out "$out" --checkpoint "$checkpoint"
"$python" "$pair/run_phase2_pilot.py" pilot --out "$out" --checkpoint "$checkpoint"
"$python" "$pair/run_phase2_pilot.py" report --out "$out" --pilot-only
```

The default weather input is `data/austria_15km`. It needs `grid_long.parquet`, `points_with_labels.csv` and `tirex2_forecasts.npz`. The existing event builder creates the labels and candidate fronts if either file is missing. Pass `--phase1-results` to use original Exp 10, Exp 3 and Exp 6 arrays when available. The default searches `data/notebooks/results`. The preflight verifies gradients and reconstruction on an observed case against the public API and records the input-token and output-receiver mapping. The runner disables TorchDynamo because some modules in the pinned source have their own compile decorators.

After the eight-case pilot, choose a worker count from the measured runtime and memory. Each shard runs a separate tracing process. Use the same shard count when retrying, and leave completed NPZs in place.

```bash
mkdir -p "$out/logs"
workers=4
pids=()
for ((i=0; i<workers; i++)); do
  "$python" "$pair/run_phase2_pilot.py" run --out "$out" --checkpoint "$checkpoint" \
    --threads 2 --batch-size 32 --shard-index "$i" --shard-count "$workers" \
    >"$out/logs/shard-$i.log" 2>&1 &
  pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
"$python" "$pair/run_phase2_pilot.py" report --out "$out" --report-dir "$pair/experiments"
test "$status" -eq 0
```

The [full figure report](experiments/REPORT.md) and its figures are in `experiments/`. The same `report` command can refresh them from the cached case archives.

## Design and output

- The standard context has 672 observed hours, followed by 24 forecast leads. The pinned checkpoint pads the input context to 2,048 hours. Lag 1 is the last observation and lead +1 is the saved Phase I forecast origin. All 24 leads use context token 63 in the default padded run. Token maps retain the native 32-hour resolution.
- The Exp 10 fallback draws 40 ordinary and 40 pre-front cases with seed 0. It spreads selection across front systems and calendar blocks. The Phase I 2.0 masking ratio and 97% above one refer to the ordinary group with the newest day removed. The 24 pulse cases are selected before tracing. The mask effect retains its sign and its °C units. Centered slopes divide the plus-minus response by the full perturbation span in °C.
- The change groups use observed +24 h minus the last observed temperature. Stable cases match season, station and origin UTC hour and minimize the distance in the standard deviation of the last 24 observed hours. The pilot reports counts where matching or data availability limits a group. The west, central and east strata span longitude below 13°, 13–15° and at least 15°.
- The front alignment uses the event builder’s station-level passage onset. Forecasts are issued at −6, 0, +3, +6 and +12 h relative to that label. For coverage, the issuance time defines the passage phase at every lead. Origins from −2 through +3 h are during passage. The level and slope interventions use the post-passage starts with at least three hours of observed cold history. The level shifts taper over six warm-side hours. The slope intervention removes a six-hour least-squares slope while retaining the final observed value.
- The Exp 6 sweep uses 1,680 hours and the Phase I drop counts and amplitudes. The two endings share the same insertion locations and the same last 24 observed hours. The faded shape applies a 12-hour half-cosine to the ending. The runner recovers the original anomaly profile from the checked-in Exp 5 figure when the saved Exp 5/6 arrays are missing. It builds a local composite if those sources are all unavailable.
- Phase I’s upstream setup uses the 40–120 and 120–240 km rings from 290° through north to 20°. The runner also repeats it with the original 1,680-hour context. Pressure is the previous 3-hour change in hPa. Wind-aligned inputs use the nearest point within 60 km and 45° of the wind-from direction. A 24-hour backward shift preserves time of day and provides an equal-length control for each feature. Wind controls use the same availability mask as the corresponding real features. The finite response applies a centered ±0.5 standard deviation change to the latest 24 hours of one covariate.
- `cases.csv` records the origin in UTC, point ID, weather group, local passage, original forecast indices when available, and experiment membership. `phase1_case_join.csv` records the exact point and origin matches. `analysis_blocks.csv` groups all stations at the same origin and every sequence of overlapping forecast windows. `phase1_skill_by_block.csv` keeps paired error sums and counts for block resampling.
- The `arrays` directory uses one atomically written archive per case. Forecasts use the quantile axis `[q10, q50, q90]`. Temperature derivatives use `[lead, lag]`, and the mask and centered perturbation results use `[perturbation, lead, lag]`. Covariate gradient hours run from oldest to newest. Branch arrays record the realized target differencing choice alongside each intervention. Gates store `[score, gate, token]` for q50(+6), q50(+24) and q50 swing. The signed mLSTM coefficients use `[head, receiver, source]`.
- The reports link the figures, sample sizes, paired and unpaired estimates, and weather-block bootstrap bounds. The eight-case run is primarily a runtime and verification sample. Use the full report for weather-cohort comparisons.
