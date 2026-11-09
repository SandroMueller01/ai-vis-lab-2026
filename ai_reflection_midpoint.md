# AI reflection — midpoint (Phase I)

**AI-aided pair (Phase I, Pair 1)**

| First name | Last name | Student ID |
|---|---|---|
| Sandro | Müller | k52010874 |
| Carlos | Elizondo | k52320897 |

Team XPL41N · Model: TiRex-2 · Task: hourly temperature forecasts for Austria
(see [`README.md`](README.md)). The detailed log is in
[`ai-interactions/phase1-ai-aided-pair.md`](ai-interactions/phase1-ai-aided-pair.md).
The notebooks in [`notebooks/`](notebooks/) replay the most important steps with code.

<!-- Written by the AI-aided pair. Each of us writes his own part below; back each point with a concrete example
     from the log (prompt, suggestion, what you did with it). Short is fine. The last section is written together. -->

## Sandro Müller

### How we used GenAI

In short, I used it for almost everything. I worked with Claude (Opus 5.5) in long
sessions, mostly as a coding agent and not just as a chat. It wrote the dataset
builders, the event labels, the smoke test, the forecast script, the whole dashboard
and most of the texts in the READMEs and PR descriptions. My part was to say what I
wanted, run everything in the Docker container, look at the numbers and the pages,
and then tell it what was wrong. That loop happened a lot.

I used it less for the questions themselves. The five Phase I questions, the 15 km
grid and the split of work with Carlos came from our team discussions, not from the
AI.

One thing that helped me a lot: every PR has an "AI usage" section. Because the chats
are gone after a session, these sections are basically my memory of what the AI did
and what I changed.

### Where it helped

Speed. A dashboard with a map, a time slider, five question pages, hover values and a
table view for every chart would not have been possible for me in two weeks without
it. Same for the data pipeline from GeoSphere.

The synthetic covariate check. My smoke test showed that adding local variables or
eight neighbouring stations changes the error by at most 0.03 K. I first thought
something in my code was broken. The AI suggested a test with random walks where the
answer is known (a past covariate that runs 12 h ahead of the target). That showed
quite clearly that TiRex-2 more or less ignores past covariates but uses future
covariates very strongly (MAE 1.46 → 0.24). Without this I would have spent Phase I
testing an idea that cannot work.

The cold-front definition. I had "8 K colder than yesterday", which says that it is
colder, not when a front arrives. The AI came up with a definition from the
literature (cooling plus pressure rise, and the passages have to move across Austria
as a line), including references, a sensitivity table and a file that lists every
candidate with the reason it was accepted or rejected. That is now the base of Q3 and
Q5.

Checks I would not have written myself. For PR #14 it ran 54 scripted browser checks
over all pages. I would never have done that by hand.

### Where it failed or misled us

Most of the problems were not obviously wrong. They looked plausible, and I only found
them because I compared with something I already knew.

It described `P0` as surface pressure. It is mean sea level pressure.

Its first cold-wave definition ("25 % of Austria in a cold drop at *any* hour of the
day") gave 42 days. We had agreed on 29. Only "at the *same* hour" gives the 29, and
it also makes more sense, because otherwise many small drops at different times add up
to a "cold wave".

It used `interpolate(limit=3)` to fill gaps. That also fills the first three hours of
a long gap, which is not what I wanted. In our data this hardly matters, but for a
shared definition it should be right.

Small numbers were off: 304 start times instead of 306, and 374 points instead of 378
in a docstring (Carlos found that one in his review).

The "Jump to" buttons on the map used the peak of the front detection. Technically
fine, but at that hour almost no point was marked on the map (for 11 May: 0 %). A
front needs about 12 h to cross Austria. Now it jumps to the hour where most points
are in the passage (97 %).

UI things the tests did not catch: overlapping axis labels, tiny text in half-width
charts, a light/dark switch that broke the map, and a dropdown you could not read in
dark mode. Carlos found three of these in his review.

What I learned from this: the AI is very good at producing something that runs and
looks finished. Whether it is *right* is a different question, and that part stayed my
job.

### How it changed our analytical decisions

The biggest change was the covariate result. My original idea was "own history, then
local variables, then upstream points, and see if it gets better". After the smoke
test I only give the model the temperature history in Phase I, and "do neighbours
help?" became an open question instead of an assumption.

The AI also suggested passing upstream stations shifted in time as *future*
covariates. I did not just take that, because it changes the task. It is a team
decision and still open.

Calibration was not really on my list at the start. The smoke test showed the 10–90 %
band covers only 58 % at cold waves, and that became one of my main threads. In the
full runs the band holds the true value 81 % of the time in normal weather and only
34 % during cold fronts, and almost all mistakes during events are too warm. The model
is about 1 °C too cold before a front and 5.3 °C too warm three hours after it.
Without the front label I could not have shown that timing.

What did not come from the AI: the questions, the decision to make every chart name
the question it answers and its owner, and leaving the "agreed" boxes in
`model-selection.md` unticked, because those are decisions for the whole team.

### Compared with the human-only pair

*(To fill in after the comparison step. Following our own rule I did not look at
Pair 2's Phase I analysis yet.)*

What I can already say: both pairs use the same 15 km dataset and the same event
labels, so the comparison is fair on the data side. But I built the shared setup (data,
labels, smoke test) with AI, so Pair 2 also builds on AI-made groundwork, even if their
analysis is human-only. I want to be honest about that in the comparison.

Things I want to compare: which questions each pair found, how long it took, and
whether Pair 2 found things I missed because I was busy building a dashboard. My guess
is that I have more breadth and more polish, and they might have looked more carefully
at fewer things. Let's see if that is true.

### What we would do differently in Phase II

Write the log during the session, not afterwards. My log is reconstructed from the PR
descriptions, so the prompts are paraphrased. Next time I copy the prompts that matter
into the log right away.

Reproduce a known number first. Almost every real bug was found this way (29 days, 306
start times, 378 points). Before I trust a new pipeline, I check one number I already
know.

Ask for a synthetic test when a result is flat or surprising. That was the most useful
single prompt of Phase I for me.

Look at the output myself. Scripted checks are nice, but they missed every layout
problem.

Smaller steps. Some sessions were very long and produced a lot at once. That is harder
to review, also for Carlos.

Advice for Pair 2 (AI-aided in Phase II): use the AI for the heavy lifting (hidden
states, gate activations, saliency code), but decide the questions yourselves, and keep
one log entry per PR with prompt, output, what you checked and what you changed.

## Carlos Elizondo

### How we used GenAI

<!-- Which tools, for which steps (code, plots, interpreting results, writing), how often. -->

### Where it helped

<!-- Concrete examples where AI made the analysis faster, broader or better. -->

### Where it failed or misled us

<!-- Wrong code, wrong claims, plausible but wrong interpretations. How did you notice? -->

### How it changed our analytical decisions

<!-- Which questions, methods or visualisations came from AI suggestions? Which did you reject, and why? -->

### Compared with the human-only pair

<!-- Same questions, different process: what did each pair find, miss, or take longer for? -->

### What we would do differently in Phase II

<!-- Practices to keep, practices to avoid, advice for Pair 2, who is AI-aided in Phase II. -->

## Together

### What we agree on

<!-- The two or three points both of us would sign. Fill in after both parts are written. -->
