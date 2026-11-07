# Midpoint submission (end of Phase I)

Deadline: **11.11.2026, 23:59**. Team XPL41N, Model: TiRex-2, Task: hourly temperature forecasts for Austria.

| Pair | Members | Phase I |
|---|---|---|
| Pair 1 | Sandro Müller (k52010874), Carlos Elizondo (k52320897) | AI-aided |
| Pair 2 | Nikolas Basios (k12323568), Maximilian Fridrich (k01608851) | human-only |

## What we hand in

| Part | Where |
|---|---|
| Code of both pairs | this repository, branch `main` |
| Pair 1: forecasts, dashboard, experiment notebooks | [`phase1-model-behavior/pair-1/`](../../phase1-model-behavior/pair-1/) |
| Pair 2: analysis | [`phase1-model-behavior/pair-2/`](../../phase1-model-behavior/pair-2/) |
| Shared groundwork: data, event labels, cold-front rule | [`data_acquisition/`](../../data_acquisition/), [`data_acquisition/events/README.md`](../../data_acquisition/events/README.md) |
| AI interaction log (AI-aided pair) | [`ai-interactions/phase1-ai-aided-pair.md`](../../ai-interactions/phase1-ai-aided-pair.md) |
| AI reflection | [`ai_reflection_midpoint.md`](../../ai_reflection_midpoint.md) |
| Cross-pair comparison | [`phase1-model-behavior/comparison.md`](../../phase1-model-behavior/comparison.md) |
| Dashboard (live) | <https://sandromueller01.github.io/ai-vis-lab-2026/> |
| Progress video (up to 5 minutes) | see below |

## Video

The video file is **not stored in git** (`*.mp4` and `*.mov` are ignored on purpose: the files are large and stay in the
history forever). It is linked here instead.

- **Link:** _to be added before the deadline_
- **Hosting:** an unlisted upload (for example JKU cloud storage or an unlisted video link) that opens without a login. Check the link in a
  private browser window.
- **Length:** at most 5 minutes.
- **What it shows:** the live dashboard, so the video matches what is deployed. Proposed structure (to be confirmed by the team):

| Time | Content | Who |
|---|---|---|
| 0:00 – 0:45 | The team, the model, the data | Sandro |
| 0:45 – 1:30 | How we find a cold front (thresholds, 16 fronts); map with the front rings | Sandro |
| 1:30 – 2:30 | What TiRex-2 reacts to: section 2 of the dashboard | Carlos |
| 2:30 – 3:30 | Limits and errors, in particular at cold fronts: section 3 | Sandro |
| 3:30 – 4:30 | Pair 2's Phase I findings | Max, Nico |
| 4:30 – 5:00 | How AI was used in Phase I, and what comes next | all |

## Checklist before submitting

- [ ] All Phase I pull requests are merged into `main` and the checks are green
- [ ] AI log of the AI-aided pair is complete, with both members' prompts
- [ ] `ai_reflection_midpoint.md` is written by the AI-aided pair
- [ ] `phase1-model-behavior/comparison.md` is filled in by both pairs
- [ ] The live dashboard opens and shows the three sections
- [ ] The video link above works in a private browser window
- [ ] Submitted on Moodle before 11.11.2026, 23:59
