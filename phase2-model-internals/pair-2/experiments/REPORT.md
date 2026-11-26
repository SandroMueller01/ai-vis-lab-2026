# Phase II TiRex-2 weather figures

**405 of 405 cases available.** Full manifest analysis.

Exp 10 cases use a seeded replacement. Phase I reported a masking ratio of 2.0 with 97% of ordinary cases above one. Exp 6 drop profile uses the anomaly composite published in Phase I Exp 5.

The forecast origin is the first forecast hour. The preceding observation is lag 1. Phase I bins use observed lead +24 minus lag 1. Curves pool cases. The estimates table weights contiguous forecast blocks equally and includes 95% block-bootstrap intervals where at least three blocks are available. A block contains all stations at an origin and contains any starts with overlapping verification windows. The Phase I skill panel weights paired forecasts equally and resamples whole blocks.

## Available cases

| Cohort | Cases | Blocks |
|---|---|---|
| Exp 10 ordinary | 40 | 34 |
| Exp 10 pre-front | 40 | 12 |
| cooling | 48 | 34 |
| stable | 48 | 26 |
| warming | 48 | 33 |
| Pulse and embedding | 24 | 20 |
| Local front alignment | 120 | 12 |
| Paired level and slope | 72 | 12 |
| Exp 6 sweep | 24 | 12 |
| Upstream covariates | 40 | 12 |

Pilot total case time was 1078.0 s. Case times ranged from 23.6 to 229.9 s and peak process RSS was 2493 MiB.

## Newest-two sensitivity ratio

| group | setup | lead | n | blocks | estimate | low | high |
|---|---|---|---|---|---|---|---|
| ordinary | fd025 | 24 | 40 | 34 | 2.094 | 1.997 | 2.195 |
| ordinary | fd025 | 32 | 40 | 34 | 2.155 | 2.053 | 2.262 |
| ordinary | fd1 | 24 | 40 | 34 | 1.689 | 1.621 | 1.764 |
| ordinary | fd1 | 32 | 40 | 34 | 1.745 | 1.672 | 1.825 |
| ordinary | gradient | 24 | 40 | 34 | 2.414 | 2.294 | 2.543 |
| ordinary | gradient | 32 | 40 | 34 | 2.485 | 2.365 | 2.616 |
| ordinary | mask | 24 | 40 | 34 | 1.871 | 1.712 | 2.036 |
| ordinary | mask | 32 | 40 | 34 | 1.909 | 1.755 | 2.074 |
| pre-front | fd025 | 24 | 40 | 12 | 2.222 | 2.152 | 2.310 |
| pre-front | fd025 | 32 | 40 | 12 | 2.302 | 2.237 | 2.390 |
| pre-front | fd1 | 24 | 40 | 12 | 1.803 | 1.746 | 1.872 |
| pre-front | fd1 | 32 | 40 | 12 | 1.879 | 1.816 | 1.949 |
| pre-front | gradient | 24 | 40 | 12 | 2.518 | 2.425 | 2.625 |
| pre-front | gradient | 32 | 40 | 12 | 2.613 | 2.521 | 2.723 |
| pre-front | mask | 24 | 40 | 12 | 2.133 | 1.851 | 2.421 |
| pre-front | mask | 32 | 40 | 12 | 2.175 | 1.858 | 2.501 |

The lead column in this table gives the number of excluded input hours. NaN masking is measured in °C, while gradients and centered finite differences measure the forecast response per degree of input change. The ratio is dimensionless.

## Newest-two ratio in embedding output changes

| panel | group | setup | n | blocks | estimate | low | high |
|---|---|---|---|---|---|---|---|
| embedding newest-two ratio | ordinary | 1 °C weather input | 12 | 12 | 2.172 | 1.929 | 2.411 |
| embedding newest-two ratio | ordinary | equal scaled input | 12 | 12 | 2.246 | 2.244 | 2.248 |
| embedding newest-two ratio | pre-front | 1 °C weather input | 12 | 10 | 2.367 | 2.169 | 2.571 |
| embedding newest-two ratio | pre-front | equal scaled input | 12 | 10 | 2.248 | 2.245 | 2.250 |

## Change by cohort at +24 h

| panel | group | setup | n | blocks | estimate | low | high |
|---|---|---|---|---|---|---|---|
| change | cooling | Forecast q50 | 48 | 34 | -0.930 | -1.307 | -0.593 |
| change | cooling | Observed | 48 | 34 | -6.668 | -7.197 | -6.180 |
| change | stable | Forecast q50 | 48 | 26 | 0.173 | -0.164 | 0.569 |
| change | stable | Observed | 48 | 26 | -0.039 | -0.336 | 0.245 |
| change | warming | Forecast q50 | 48 | 33 | 1.202 | 0.578 | 1.937 |
| change | warming | Observed | 48 | 33 | 5.979 | 5.672 | 6.343 |

## Level and swing responses

| panel | group | setup | n | blocks | estimate | low | high |
|---|---|---|---|---|---|---|---|
| forecast level response | passage +12 h | Remove recent slope | 24 | 12 | -0.211 | -0.365 | -0.071 |
| forecast level response | passage +12 h | Warm prefix +3 °C | 24 | 12 | 0.523 | 0.317 | 0.730 |
| forecast level response | passage +12 h | Warm prefix −3 °C | 24 | 12 | -0.697 | -0.921 | -0.463 |
| forecast level response | passage +3 h | Remove recent slope | 24 | 12 | -0.064 | -0.375 | 0.265 |
| forecast level response | passage +3 h | Warm prefix +3 °C | 24 | 12 | 1.116 | 0.917 | 1.345 |
| forecast level response | passage +3 h | Warm prefix −3 °C | 24 | 12 | -1.303 | -1.498 | -1.121 |
| forecast level response | passage +6 h | Remove recent slope | 24 | 12 | 0.063 | -0.019 | 0.181 |
| forecast level response | passage +6 h | Warm prefix +3 °C | 24 | 12 | 0.846 | 0.668 | 1.032 |
| forecast level response | passage +6 h | Warm prefix −3 °C | 24 | 12 | -1.175 | -1.330 | -0.978 |
| forecast swing response | passage +12 h | Remove recent slope | 24 | 12 | -0.226 | -0.378 | -0.097 |
| forecast swing response | passage +12 h | Warm prefix +3 °C | 24 | 12 | 0.724 | 0.528 | 0.958 |
| forecast swing response | passage +12 h | Warm prefix −3 °C | 24 | 12 | -0.982 | -1.271 | -0.723 |
| forecast swing response | passage +3 h | Remove recent slope | 24 | 12 | -0.335 | -0.617 | -0.084 |
| forecast swing response | passage +3 h | Warm prefix +3 °C | 24 | 12 | 1.313 | 1.084 | 1.535 |
| forecast swing response | passage +3 h | Warm prefix −3 °C | 24 | 12 | -1.468 | -1.623 | -1.310 |
| forecast swing response | passage +6 h | Remove recent slope | 24 | 12 | -0.187 | -0.400 | -0.021 |
| forecast swing response | passage +6 h | Warm prefix +3 °C | 24 | 12 | 0.913 | 0.691 | 1.127 |
| forecast swing response | passage +6 h | Warm prefix −3 °C | 24 | 12 | -1.194 | -1.380 | -0.997 |

## Interval diagnostics at +12 h by issuance phase

| panel | group | setup | n | blocks | estimate | low | high |
|---|---|---|---|---|---|---|---|
| above | after | base | 48 | 12 | 0.042 | 0.000 | 0.125 |
| above | before | base | 127 | 12 | 0.000 | 0.000 | 0.000 |
| above | during | base | 48 | 12 | 0.010 | 0.000 | 0.031 |
| above | stable | base | 48 | 26 | 0.010 | 0.000 | 0.029 |
| below | after | base | 48 | 12 | 0.174 | 0.042 | 0.340 |
| below | before | base | 127 | 12 | 0.700 | 0.549 | 0.850 |
| below | during | base | 48 | 12 | 0.378 | 0.198 | 0.580 |
| below | stable | base | 48 | 26 | 0.051 | 0.000 | 0.141 |
| inside | after | base | 48 | 12 | 0.785 | 0.618 | 0.931 |
| inside | before | base | 127 | 12 | 0.300 | 0.153 | 0.456 |
| inside | during | base | 48 | 12 | 0.611 | 0.424 | 0.778 |
| inside | stable | base | 48 | 26 | 0.939 | 0.849 | 1.000 |
| median bias | after | base | 48 | 12 | 1.049 | 0.094 | 2.055 |
| median bias | before | base | 127 | 12 | 5.593 | 4.416 | 6.847 |
| median bias | during | base | 48 | 12 | 2.570 | 1.557 | 3.581 |
| median bias | stable | base | 48 | 26 | 0.149 | -0.457 | 0.782 |
| width | after | base | 48 | 12 | 6.513 | 6.029 | 6.975 |
| width | before | base | 127 | 12 | 7.117 | 6.433 | 7.826 |
| width | during | base | 48 | 12 | 6.671 | 6.075 | 7.285 |
| width | stable | base | 48 | 26 | 6.169 | 5.662 | 6.671 |

## Figures and estimates

- [Signed and folded temperature sensitivity](01_patch_heatmaps.png)
- [Gradient, masking and finite-difference controls](02_patch_controls.png)
- [Gradient profiles by season and region](02_patch_strata.png)
- [Cooling pulse and embedding responses](02_pulse_embedding.png)
- [Forecasts aligned to local passage](03_front_alignment.png)
- [Predicted and observed changes](03_change_cohorts.png)
- [Level and slope interventions](03_level_slope.png)
- [sLSTM gate saliency and memory flow](03_internal_gates.png)
- [Signed mLSTM coefficients by head](03_internal_heads.png)
- [Lead-matched coverage, width and bias](04_coverage.png)
- [Covered and missed case saliency](04_coverage_saliency.png)
- [Exp 6 abrupt and faded drop sweeps](04_drop_sweep.png)
- [Pressure, upstream and shifted controls](05_upstream.png)
- [Synthetic warning flag response](05_synthetic_warning.png)
- [Phase I baseline skill and Phase II sensitivity](06_skill.png)
- [Block-level estimates](by_event_or_block.csv)
- [Bootstrap estimates](estimates.csv)
- [Preprocessing branch changes](branch_changes.csv)
- [Original Phase I lead skill](phase1_lead_skill.csv)
- [Cases included](reported_cases.csv)
- [Case manifest](../../../data/tirex2-phase2/cases.csv)
- [Real-weather preflight](../../../data/tirex2-phase2/preflight.json)
- [Signed arrays and intervention forecasts](../../../data/tirex2-phase2/arrays/)
