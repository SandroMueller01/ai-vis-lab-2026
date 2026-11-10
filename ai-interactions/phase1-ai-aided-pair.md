# AI Interaction Log — Phase I, AI-aided pair

Pair: Pair 1 (Sandro Müller, Carlos Elizondo)
Phase: I (model behavior)

## How to read this log

- **Two parts, one per person:** Sandro's and Carlos's, in the same format: how we used AI, the important prompts, what we accepted, modified or rejected, failure patterns, best practices.
- **Prompts are quoted as typed**, with typos. `[…]` marks a shortened prompt, `[pasted]` a pasted text.
- The assistant sessions in Sandro's part ran on his computer. Carlos's part is written by him.
- The log is based on the chat history and the pull requests, and was checked by both of us in the pull request.

## How we worked with the AI

We used an AI coding assistant in the editor, with access to the repository, the data and a Docker container. The assistant wrote and ran
code, searched the literature and drafted texts. We decided what to build, what to keep and what goes into the repository, ran and checked
the results and made every commit and push ourselves. Each step ended in a pull request that a teammate reviewed.

## What the AI let us do beyond a baseline

Generative AI made it cheap to try more than the minimum. We used that in two directions.

**Broader analysis**

- **Ten experiments instead of one or two.** Carlos's Exp 1 to 11 (Exp 8 was dropped) change the model's input in controlled ways: repeated and one-off patterns, history length, time inputs, extra variables, upwind points, the time after a front, strange history, which hours the model uses, and whether its band is honest.
- **A full evaluation, not a demo.** 336 forecast start times at 378 points, against two baselines ("same as yesterday", "same as an hour ago"), split into normal weather and 30 cold-front runs.
- **A cold-front rule from the literature.** Instead of a simple cold-drop label, a front needs a cooling, a pressure rise and a moving line (16 fronts on 15 km).
- **Checks of our own claims.** Findings were re-run on more dates (Carlos) and cross-checked between the two of us (for example his "21 % of the drop").

**Richer interaction**

- **Map with a time slider.** The 15 km grid (378 points), a day picker with an hourly slider, seven variables, event rings for cold fronts and a chart for every clicked point.
- **A story page with scrollytelling.** A pinned section that scrolls sideways, then chapters where the text steps scroll past and the figure changes with them.
- **Hover and explanations.** Every chart shows values on hover; "i" buttons explain how to read it.
- **Explore it yourself.** Carlos's per-front explorer, where one chooses a front and sees which points the forecast missed and where. His Martini-glass idea (an overview first, details on demand) was the design goal for the story page.
- **Questions named on every chart**, so each figure says what it is meant to answer.

Section "Record over time" in Sandro's part shows in which order this happened.

## From questions to experiments

The short version of Phase I: **each question we asked sent us to an experiment, and each result raised the next question.**
The steps below follow that chain and show what the assistant contributed at each point. The results themselves (findings and key plots) are in the
[experiments README](../phase1-model-behavior/pair-1/experiments/README.md#results-at-a-glance).

### Step 1 · Can we feed the model neighbouring stations? (Sandro, 27 Oct to 2 Nov)

```
goal: temperature change at several stations  →  smoke test  →  TiRex-2 ignores past covariates
   →  "how does the model behave?" (hypotheses B1 to B4)  →  15 km grid  →  cold-front label  →  336 runs
```

| Question that came up | What we did with the assistant | What we found | Where to see it |
|---|---|---|---|
| Can neighbours help predict a cold wave? | Smoke test on 12 points with and without covariates | Only *future* covariates change the forecast; past ones are ignored | `scripts/tirex_smoke_test.py` |
| So what should Phase I be? | The assistant proposed four behaviour hypotheses | We switched from "predict with many inputs" to **how the model behaves** | Behaviour hypotheses B1 to B4 (shared in the team chat) |
| Which horizon is good? Where does it fail on a map? | Side-by-side maps, real data against forecast | The forecast follows the front late; 12 h is the best compromise | Dashboard, *Explore* map |
| Is our "cold drop" a cold front? | Literature search on front definitions | No: a front needs cooling, a pressure rise and a line that moves | Cold-front rule in the dashboard overview |

### Step 2 · Sandro's five questions on 336 forecasts (2 to 4 Nov)

The results are in the [experiments README](../phase1-model-behavior/pair-1/experiments/README.md#results-at-a-glance). Here: what the assistant contributed and what we decided.

| Step | What the assistant suggested | What we decided |
|---|---|---|
| The five questions | At first nothing: it assumed Sandro was in the human-only pair and held back until the roles were corrected | The questions came from us (the Phase I plan and the team meeting); Sandro asked for sources with every answer |
| The evaluation | Baselines ("same as yesterday", "same as an hour ago"), the 2 °C rule for a mistake, 16 situations, 336 start times | Accepted. Run on the 15 km grid, 378 points |
| The text of the answers | A first text with placeholders for the numbers | Placeholders kept until the run was done; three statements changed after it |
| The dashboard | A plan with milestones, then nine candidate figures and a six-page structure | We kept what answers a question and named that question on every chart |
| Overlap with Carlos's findings | A cross-check of his "21 % of the drop" against our runs | We keep our charts and mark the owner; overlapping charts link to his finding and back |

### Step 3 · Carlos's experiments (Exp 1 to 11)

Carlos's ideas came from the lectures and his own brainstorming; the assistant shaped them into set-ups. What he asked for, and what he
accepted, changed or rejected, is in his own part below. The results of the experiments are in the
[experiments README](../phase1-model-behavior/pair-1/experiments/README.md#results-at-a-glance).

## Sandro Müller

#### Student ID K52010874 · GitHub SandroMueller01
#### Phase I work: repository set-up, data and event labels, the TiRex-2 smoke test, the 336 forecast runs with the five questions (*Limits* and *Errors*), the dashboard and its deployment.

### How I used AI

I used an AI coding assistant in the editor, with access to the repo, the data and the Docker container.

1. **Goal and decisions first.** I set the goals and the rules (for example the change of the goal to temperature change at several stations, the 15 km grid, no password on the dashboard, no tool traces in the repo). The assistant proposed options, I chose.
2. **Building.** The assistant wrote and ran the code (Docker and CI, dataset builders, smoke test, forecast runs, dashboard) and drafted texts (PR texts, Discord messages, answers with sources).
3. **Checking.** I asked for a source with every claim and for the numbers behind it. Dashboard changes were tested with a scripted browser, not only with screenshots.
4. **Review.** Every step ended in a pull request that a teammate reviewed. I made every commit and push myself.

### Important prompts

Prompts are quoted as typed, with typos; `[…]` marks a shortened prompt.

| When | Prompt | What it led to |
|---|---|---|
| 20 Oct | "Okay the thing is that I do not want that you leave a trace behind that it cannot be seen on the repo that commits and pushes and stuff like this happend with […]" | `WAYS_OF_DEV_WORKING.md` with branch and commit prefixes; I do the commits and pushes. |
| 23 Oct | "[…] we want to change the goal, to basically guess th temperature change with TiReX2 and checkout how multiple station input wo […]" | A smoke test (12 points). TiRex-2 ignores *past* covariates and only uses *future* ones. The work turned from "predict with many inputs" into **how the model behaves** (hypotheses B1 to B4). |
| 26 Oct | "Okay can we please create some visualisation of austria and show casing how the cold distributes through austria the real data and the predicted from TiRex 2 model side b […]" and "what would be a a good horizon for guessing?" | The forecast follows the front late; 12 h is the best compromise. The idea of the time-slider dashboard. |
| 1 Nov | "Okay I guess this is phase 1 we settled on that: [pasted] Phase 1 Data a coarser grid over all of Austria […]" | Three grid options with run times; **15 km, 378 points** and a shared release for the whole team. |
| 1 Nov | "Can you take a look at the definition of cold fronts is there any research we can find about that and if yes how they define cold fronts?" | Our `cold_drop` (8 K colder than yesterday) is not a front. A separate `cold_front` label: 3 K in 3 h, 2 hPa, a moving line, at least 50 % of points within 24 h. 16 fronts on 15 km. Every cold-front chart rests on it. |
| 2 Nov | "Can you help me to answer the following questions, should be backed up with data and science everytime. […]" | The five questions, the 336 forecasts and a source for each answer. After the run, three statements changed (see below). |
| 2 Nov | "No we are AI in the first phase we are pair one please check the github that it is written everywhere correct" | The assistant had followed the older plan (AI-aided in Phase II) and held back on the Phase I questions. Roles corrected in the README, the logs and the PR texts. |
| 2 Nov | "okay there should be no password. Github pages sounds good. This can you do as you want. keep the 3d as a last step […]" | Public page, GitHub Pages, no 3D view. The data is open (CC BY 4.0) and the repo is public. |
| 4 Nov | "Okay please make it in a way that the dashboard has multiple pages an please als name the question which are answered by each viusalation […]" | Six pages with the question named on every chart. |
| 4 Nov | "okay because these were the questions carlos tried to answer so we should not duplicate the questions if you get what I mean […]" | Cross-check of Carlos's "21 % of the drop": about 0 % when the front is 4 or more hours away, 19 to 40 % at 1 to 3 hours. We keep our charts and mark the owner. |

### Record over time

What happened when, with the pull request it ended in. Dates are the days the work was done or merged.

| Date | What we did with the assistant | Ended in |
|---|---|---|
| 20 Oct | Docker image, dev container, CI, PR template; rule that the repo shows no tool traces; dataset builders; pairs entered in the README | PRs #1 to #3, `WAYS_OF_DEV_WORKING.md` |
| 23 Oct | New goal (temperature change, several stations); first review of a teammate's PR | model selection (PR #5) |
| 24 Oct | Smoke test: TiRex-2 ignores past covariates; behaviour hypotheses B1 to B4 written for the team | smoke test (PR #8) |
| 26 Oct | Maps and time-longitude plots of the 25/26 March front, real data against forecast; 12 h chosen as the main horizon; first time-slider preview | local preview (not in the repo) |
| 27 to 29 Oct | Data acquisition reviewed for the new goal; shared event labels; release kept and renamed; agenda for the team meeting | PRs #9, #10 |
| 1 to 2 Nov | Three grid options, 15 km chosen; literature search on cold fronts and the `cold_front` label | 15 km dataset and labels (PR #11) |
| 2 Nov | The five questions; 336 forecasts started; pair roles corrected; dashboard milestone 1 (map, slider, variables, event rings) | PRs #12, #13 |
| 4 Nov | Carlos's review of the map fixed; candidate figures; six pages with the question named on every chart; overlap with Carlos's findings checked; GitHub Pages switched on | PRs #13, #14, #4, #7, #10 |
| 5 Nov | README and model selection updated | PR #15 |
| 6 to 7 Nov | Carlos's experiment notebooks and the replay notebooks; the one-page story dashboard; three sections with sideways scrolling, then vertical scrolling again after review; richer figures for the two experiments we picked | PRs #17 to #22 |
| 7 to 9 Nov | Submission README and video information; split of the reflection into sections per person | PRs #16, #23, #24 |

### Accepted, modified, rejected

| Suggestion from the AI | Outcome | Why |
|---|---|---|
| 15 km lattice for Phase I | Accepted | A few hundred points; a run takes about 15 s |
| Separate `cold_front` label from the literature | Accepted | A cold drop is not a front |
| Keep the data release and only rename it | Accepted | The data is still used |
| Password on the preview dashboard | Rejected | The data is open (CC BY 4.0) and the repo is public |
| Light and dark map with a switch | Rejected after Carlos's review | The switch broke the map; dark only |
| Slider over the whole year | Modified after Carlos's review | Too coarse; now day picker plus a 24-hour slider |
| Neighbours as future values | Not used as a result | Future values of other stations are not known at forecast time, so they only give an upper bound. Carlos's tests show that past inputs give no gain |
| Keep our charts and mark the owner when they overlap with Carlos's questions | Accepted | Nothing is removed; each overlapping chart links to his finding and back |

### How AI suggestions affected my decisions

- **Cold fronts.** The literature search led from the `cold_drop` label to a separate `cold_front` label.
- **Horizon.** The smoke test and the maps led to 12 hours as the main horizon.
- **Grid.** Three options with run times; I chose 15 km, 378 points.
- **Answers.** The first text had placeholders. After the forecast run three statements changed: at 24 h TiRex-2 is still slightly better than "same as yesterday", the statement about regions changed (see the overclaims below), and most large mistakes in normal weather are too cold.
- **Dashboard.** The five questions structure it; Carlos's review changed the time control and the theme.

### Failure patterns

- **Pair roles.** On 20 October the plan was that Sandro and Carlos are AI-aided in Phase II. On 1 and 2 November the repo and I said Phase I. The assistant first followed the older state and held back on the Phase I questions until it was corrected. The change of the roles was agreed in a team meeting between 20 October and 1 November.
- **Usage limit.** One question got no answer because the assistant had reached a usage limit; it was answered the next day.
- **Wrong numbers in its own summary.** It reported "304 start times plus 32 front runs". The data has 306 plus 30. Found when the dashboard data was built from the file.
- **Plausible but wrong presets.** The first "jump to" times used the peak of the front detection, where almost no point was marked. Changed to the hour with most points in the passage.
- **Screenshots can mislead.** Headless screenshots sometimes showed a blank map. We tested with a scripted browser session instead.
- **Overclaims.** A sentence said the dashboard "works on a phone" before it was tested. Removed. A statement that errors are lowest in the Alps was also taken out of the dashboard text because the data did not show it clearly enough.
- **Sources from memory.** Two author names and some page numbers came from search snippets or memory. They were flagged and are still to be checked.
- **Blocked access.** The API check failed because of a certificate proxy; the assistant did not bypass it. It also could not edit the GitHub release itself (permission), so I ran that command.
- **Text before data.** The first answers contained numbers from an older test (58 % band coverage). They were replaced by numbers from the new run.
- **An inconclusive first check.** The first cross-check of Carlos's "21 % of the drop" mixed the normal evening cooling into the drop and gave numbers between −15 % and 76 %. It was redone against yesterday's temperature at the same hour.
- **A bug that lost links.** The links to Carlos's questions on our charts were silently dropped by a bug in the element builder. The scripted browser test found it.
- **Found only by the reviewer.** The docstring of `build_subset.py` said 374 points instead of 378. Carlos found it in his review of PR #11.
- **Squash merges cause conflicts.** After PR #13 was squash-merged, the stacked branches conflicted and had to be merged with `main`.

### Best practices

- Ask for a source with every claim, and mark what could not be checked.
- Write the text after the numbers are computed; keep placeholders until then.
- Test the interface with a scripted browser, not only with screenshots.
- Keep one definition of an event in one place (the event script) and reuse it.
- Say who is human-only and who is AI-aided in every README and every log, and check it after every change.
- Small pull requests with an honest AI usage section and a reviewer who has read the code.
- A second pair of eyes finds what the author misses: Carlos's review of the dashboard and of the 15 km dataset each found a real problem.

## Carlos Elizondo

#### Student ID K52320897 · GitHub erca-2064
#### Phase I work: experiments in `phase1-model-behavior/pair-1/experiments/` (Exp 1–11) and the story pages of the dashboard.

### How I used AI

I used an AI coding assistant / agent in VS Code, with access to the repo, the data and the Docker container.

1. **Ideas first, without AI.** I watched the Phase I lectures, brainstormed experiments on my own and agreed on them with Sandro, then we splitted the work. The ideas started as broad questions, for example: "if one whole day a week ago were a constant 10 °C (or 100 °C), how would today's forecast change?"
2. **Context for the assistant.** I explained the dataset, the model and the course setting: in Phase I we treat TiRex-2 as a black box, change only its input and watch the output.
3. **Shaping the experiments.** With the assistant, the broad questions became defined experiments (setups, measures, sample sizes), and then besides the brainstormed ideas the AI analyzed which paths were pending to investigate. The coding agent designed a jupiter notebook for one question, ran the experiments on it and then I analyzed / polished it, then moved to the next questions following the same workflow. Similarly for the dashboard, it created an initial version of it with my detailed prompt and then I suggested multiple corrections until the current version.
4. **Figures.** I reviewed every result figure by figure, decided what to keep and asked for changes.

To keep the focus on the questions, the assistant was told not to suggest side experiments. It was told to only say "there is an idea regarding ..., want me to describe it?", and I decided whether to do it or not. Other rules: ask before long runs, never push to GitHub; I made every commit and push.

### Important prompts

| Prompt | What it led to |
|---|---|
| "Again, you are drifting into the problem of suggesting too many things and we don't get to certain ideas. […]" | One question at a time; the follow-up test plan was cut down. |
| "[…] this model is well studied. There is clear documentation about how it's used […] maybe we look into that first before doing a lot of tests." | The assistant read the TiRex-2 docs before designing tests. Became a standing rule. |
| "[…] I don't want directly to that you make conclusions from Sandro's smoke test. […]" | Rejected "use temperature only, the weather variables didn't help" (based on 12 points). Varying the inputs became a method of Phase I (Exp 3, 4). |
| "this quick finding, how did you get to it? because I cant just trust that what you said is right." | The assistant showed the code and how to check the number in the figure. I check claims this way since. |
| "ok wait, so are you sure that this is a weather pattern (to have warming before cold fronts)? or are you just trying to make sense out of it?" | The claim was checked against the data: warming before the drop in about half of the passages, not "every case". |
| "[…] The dataset needs to be large enough that any pattern you report can be shown to be systematic behavior, not a handful of cherry-picked examples. […]" | Exp 1 rerun on 40 dates instead of 1. The headline changed (see below). |
| "why 269 cases? did you even consider if averaging over all those cases makes sense?" | The 269 cases were 15 fronts × many points, with very different band widths. Shown as the change per case instead of a plain average. |

### Accepted, modified, rejected

| Suggestion from the AI | Outcome | Why |
|---|---|---|
| Treat "the model ignores neighbours" as a finding instead of tuning further | Accepted | All documented ways of passing neighbours were tested; Exp 3 and 4 confirmed it|
| Reframe "does it notice Sundays" as "does it learn a 7-day pattern", with a copy score | Accepted | Sharper question; became Exp 1 |
| A yes/no "closer to the Sunday value" score per hour | Modified | 49 vs 51 should not flip the result; now a continuous score from 0 to 100 % |
| Several new measures and a Martini-glass explorer for Exp 1 at once | Modified | Kept one measure; the Martini glass came later, in the dashboard |
| Region maps (mountains vs lowlands) for the Sunday effect | Rejected | No link between region and the manipulation |
| "Use temperature only" after the smoke test | Rejected | Over-generalised from 12 points |
| Click a dot in a box plot to open that case | Rejected | 800 jittered dots per box: tiny, overlapping, random pick. A fixed pair of examples instead |
| A daily climate spiral (angle = hour, radius = temperature) | Rejected after seeing it | Added nothing. The time curves were kept |
| Do not interpolate between slider steps; compute real forecasts every 0.25 °C | Accepted | Interpolated bands would show forecasts the model never made |

### How AI suggestions affected my decisions

- **Many dates, not many points.** The assistant showed with saved results that splitting by dates changes the result and splitting by points does not. All later runs used many dates.


### Failure patterns

- **Explaining before checking.** Plausible stories stated as facts: "shared past weather" for the bright cells (really the 32-hour blocks), "this warming is in every case" (about half), "earlier runs predict a fall" (it was the normal evening cooling).
- **Not looking at its own figures.** It said figures were ready after only checking that the code ran: squashed time curves, a reversed axis, a colour bar on top of an axis. Fixed by making it screenshot every figure before reporting.
- **Summarising from numbers, not the figure.** "Fronts and normal days look alike" from printed shares, while the figure showed fronts react about 1.5× more.
- **Over-generalising from small tests.** The 12-point smoke test; a 6-case test that suggested time inputs help (they do not on 2,400 cases).
- **Inflated numbers.** The 32-hour ratio was first 2.5×; it included the last day and the front cases. Without them it is 2.0× (above 1× in 97 % of the cases).

### Best practices

- Ask for the sample size and setup behind every claim, and for the code that produced a number.
- Make the assistant check facts in the data, not from memory.
- Look at every figure myself and record a decision per figure; make the assistant screenshot its figures before it
  says they are ready.
- When a figure confuses me, ask which question it answers; this found real bugs.
- Run a quick small test before every long run, but never conclude from it.

### Reflection

- **New alternatives.** Yes, mainly in methods: occlusion ("which hours does it use"), calibration by situation and the copy score came from the assistant.
- **Criticism of my choices.** Justified when it rested on data: running all points would add little, dates matter more.
- **Confidence.** Higher for results that survived a check I asked for (40 dates, per-case changes, the 2.0× ratio). Lower for anything the assistant only described: I learned to treat its first explanation as a hypothesis.
- **Interpreting patterns.** It was fast at quantifying a pattern I saw (the 32-hour blocks, the band peaking at medium drop sizes), but the patterns themselves were found by me looking at the figures.