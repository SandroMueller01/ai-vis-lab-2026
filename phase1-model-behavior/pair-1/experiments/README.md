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

## Results at a glance

Each row: the question, the experiment, the plot that carries the finding, and what the result changed. The interactive plots are HTML files
in [`figures/`](figures/) (download and open in a browser); the others are chapters of the [dashboard](../dashboard/).

### Carlos's experiments (Exp 1 to 11)

| Question that came up | Experiment · key plot | What the record says | What it led to |
|---|---|---|---|
| Does the model copy a pattern it has seen repeatedly, and ignore one it has seen once? | Exp 1 · [`exp1_score_by_date`](figures/exp1/exp1_score_by_date.html) | A repeated pattern is copied (52–94 %), a single one ignored (~2 %); the rerun on 40 dates instead of 1 changed the headline | Rule: many dates, not many points |
| Does a longer history, or telling it the time, help? | Exp 2 · [`exp2_error_vs_history`](figures/exp2/exp2_error_vs_history.html) | History length barely matters; time inputs do not help on 2,400 cases (a 6-case test had suggested they do) | Never conclude from a small test |
| Can it see a cold front coming? Do upwind points or other variables help? | Exp 3 and 4 · [`exp3_average_front`](figures/exp3/exp3_average_front.html), [`exp4_upstream_map`](figures/exp4/exp4_upstream_map.html) | It catches only about 21 % of the drop, and no extra input changes that; it ignores neighbours | "Ignores neighbours" counted as a finding, not tuned further |
| What happens after the front? | Exp 5 · [`exp5_does_cold_last`](figures/exp5/exp5_does_cold_last.html) | Once it has seen the drop it keeps the cold; 1–2 days later its error is as small as on normal days | Dashboard: *Catching up, lasting cold* |
| Does a stranger history make it less sure? | Exp 6 · [`exp6_drops_lines`](figures/exp6/exp6_drops_lines.html) | The band is widest at medium drop sizes | Dashboard section 2: stranger history, wider band |
| How does a front change whole maps over time? | Exp 7 · [`exp7_reality_vs_forecast`](figures/exp7/exp7_reality_vs_forecast.html) | The whole map changes within hours and stays changed for days; map error peaks at 7.5 °C | Dashboard: *Time curve* |
| How do successive forecasts change as a front approaches? | Exp 9 · [`exp9_successive_runs`](figures/exp9/exp9_successive_runs.html) | The error for the front hour stays at 5–7.6 °C until about 3 h before: it sees the front only once the drop has started | Not in the dashboard (same message as Exp 3) |
| Which part of its history does it use? | Exp 10 · [`exp10_lag_vs_forecast_hour`](figures/exp10/exp10_lag_vs_forecast_hour.html) | The hours that matter repeat every 32 hours (ratio 2.0 times, above 1 in 97 % of cases) | Dashboard section 2: *Which hours it uses* |
| Does it know when it is unsure? | Exp 11 · [`exp11_pit_histograms`](figures/exp11/exp11_pit_histograms.html) | Honest on normal days (79 % inside the band); with a front coming, half the hours fall below the whole band | Dashboard: *honest band* |

### Sandro's five questions on 336 forecasts

| Question | Experiment | Key plot | Finding | Led to |
|---|---|---|---|---|
| How good is it, and is that better than doing nothing? | 336 starts, baselines "same as yesterday" and "same as an hour ago" | Dashboard section 3, chapter *How much better is it than "same as yesterday"?* (lines for the three forecasts, the gap shaded) | 25 % better at 12 h, only 5 % at 24 h | The *Limits* chapter of the dashboard: the gain shrinks with the horizon |
| Is the band honest? | Coverage of the 10 to 90 % band in normal weather | Band coverage chart (*Also tested*; the same chart around a front is the lower panel of the front chapter) | 81 % against a target of 80 % | The band is fine in calm weather, so the interesting case is fronts |
| What happens at a cold front? | 30 front runs against 306 normal starts | Same chapter, upper panel (error with the front marked) | About 5.3 °C too warm 3 h after the front arrives; band holds only 32 % | The statement "the model holds on to the old weather" |
| How often is it wrong, and where? | Error by hours ahead, by region and by weather situation | Pages Q1 to Q5 (*Also tested*) | 22 % of forecasts are wrong by more than 2 K up to 12 h, 41 % at 13 to 24 h | Three statements changed after the run (see the [AI log](../../../ai-interactions/phase1-ai-aided-pair.md)) |

### Where the two lines meet

Carlos's experiments look at *what the model uses* (it ignores neighbours, it uses hours in a 32-hour rhythm). Sandro's runs measure
*how much that costs* (5.3 °C too warm 3 h after a front arrives, band holds 32 %). The dashboard puts both into one story:
section 2 for Carlos's experiments, section 3 for the two Sandro picked.
