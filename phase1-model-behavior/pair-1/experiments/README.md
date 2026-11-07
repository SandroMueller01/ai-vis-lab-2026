# Phase I experiments: how does TiRex-2 forecast temperature?

Black-box experiments on TiRex-2 (zero-shot, 24 h temperature forecasts) with the Austria 15 km INCA dataset
(378 points, hourly, Oct 2025 - Sep 2026). Each experiment changes the **input** in a controlled way and
looks at what happens to the **output** (forecast median and 10-90 % band).

**How to look at the figures**
- GitHub cannot show the interactive (Plotly) figures inside the notebooks; open the notebooks in VS Code or
  Jupyter to see them.
- The interactive versions (hover, sliders, zoom) are the HTML files in [`figures/`](figures/), one subfolder per
  experiment. GitHub shows HTML as source code, so download the file and open it in a browser.
- The notebooks contain all code and results. Run them in the project container (see the main README).
  Saved forecasts go to `data/notebooks/results/` (not in git, ~63 MB) and are reloaded instead of recomputed;
  without them a notebook recomputes its forecasts (from minutes up to ~3 h for Experiment 7).

| # | Notebook | Question |
|---|---|---|
| 1 | [exp1_fixed_sundays](exp1_fixed_sundays.ipynb) | Does the model continue a pattern it has seen repeatedly, and ignore one it has seen once? |
| 2 | [exp2_history_length](exp2_history_length.ipynb) | Does a longer history, or telling the model the time, help? |
| 3 | [exp3_front_tells](exp3_front_tells.ipynb) | Can the model see a cold front coming, and how does it react once it is there? |
| 4 | [exp4_changes_upstream](exp4_changes_upstream.ipynb) | Do weather changes or upwind points help it see a cold front? |
| 5 | [exp5_after_the_front](exp5_after_the_front.ipynb) | What happens after a cold front? |
| 6 | [exp6_weird_context](exp6_weird_context.ipynb) | Does a stranger history make the model less sure? |
| 7 | [exp7_time_curves](exp7_time_curves.ipynb) | How does a cold front change Austria's weather (time curve of whole maps)? |
| 9 | [exp9_forecast_evolution](exp9_forecast_evolution.ipynb) | How do successive forecasts change as a front approaches? |
| 10 | [exp10_where_tirex_looks](exp10_where_tirex_looks.ipynb) | Which part of its history does the model use? |
| 11 | [exp11_band_honesty](exp11_band_honesty.ipynb) | Does the model know when it is unsure? |

(Experiment 8 was dropped.)

Sandro's part of Phase I (the 336 forecast runs and the five questions behind the *Limits* and *Errors* sections of the dashboard) is in [phase1_forecast_results.ipynb](phase1_forecast_results.ipynb).
