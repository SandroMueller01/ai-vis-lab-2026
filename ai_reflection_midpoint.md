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

I used it mainly for two things: setting up the repository (Docker, CI, the PR
workflow, the data release) and working out ideas (the new goal, the cold-front
definition, the evaluation, the plan for the dashboard). I worked with Claude
(Opus 5.5) in sessions in the editor, not just as a chat. For the code that followed
(dataset builders, smoke test, forecast script, dashboard) it did the first version.
My part was to say what I wanted, run everything in the Docker container, look at the
numbers and the pages, and then tell it what was wrong. That loop happened a lot.

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
32 % during cold fronts, and almost all mistakes during events are too warm. The model
is about 1 °C too cold before a front and 5.3 °C too warm three hours after it.
Without the front label I could not have shown that timing.

What did not come from the AI: the questions, the decision to make every chart name
the question it answers, and leaving the "agreed" boxes in
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

In Phase II our pair works without AI, so this is what I take over from Phase I, and
what I would tell Pair 2, who is AI-aided in Phase II.

What I take over into Phase II:

Reproduce a known number first. Almost every real bug was found this way (29 days, 306
start times, 378 points). Before I trust a new pipeline, I check one number I already
know.

Test with synthetic data when a result is flat or surprising. The random-walk test was
the most useful single step of Phase I for me, and it works just as well without AI.

Smaller steps. Some sessions in Phase I were very long and produced a lot at once.
That is harder to review, also for Carlos. Small pull requests are easier to check,
with or without AI.

Advice for Pair 2 (AI-aided in Phase II): write the log during the session, not
afterwards, and copy the prompts that matter right away. Use the AI for the heavy
lifting (hidden states, gate activations, saliency code), but decide the questions
yourselves, and keep one log entry per PR with prompt, output, what you checked and
what you changed.

## Carlos Elizondo

**How I worked with it.** The ideas for my experiments came from the lectures, my own brainstorming and the
discussions with Sandro. The AI turned them into concrete set-ups, wrote and ran the code and made the figures; I
reviewed every result and decided what to keep. Over the two weeks I learned that I could not take its conclusions as
they came. Whenever I asked how many points or dates a result was based on, or whether it still holds if we include
this or that, the answer was often "sorry, I overlooked that" or "do you want me to run another experiment?". That
lowered my confidence in its conclusions. So I trusted it differently depending on the task. The dashboard I can
click through and see that it works, so I did not care much how its code looked. For the experiments the conclusion
is the result, and the only way to check it is to read the code and the reasoning behind it, so there I looked much
closer.

**Where it helped.** Speed, mostly in designing experiments and building visualizations. Without it, finding out how
such things are usually done would have taken much more time and research, and a big part of the dashboard code was
written by the AI. It also brought in methods I would maybe have found myself, but only after a lot of reading that
the deadline did not allow. The best example is hiding certain hours of the history and measuring how the forecast
changes, to see how important each hour is (Exp 10). That design came from the AI.

**Where it failed.** It drew conclusions from smoke tests. You cannot generalise from 12
points, even with a very capable model. Many times I had to write in the prompt that it should look at other angles,
question itself and be analytical. If I had just followed it, it would have built a chain of small errors and
inconsistencies, and I would have built the story of the project on top of them.

**How it changed my decisions.** Mostly by forcing me to question its suggestions. For the fixed-Sundays experiment
it proposed maps of the effect by region (mountains vs lowlands). It sounds like a richer analysis, but there is no
reason why changing the temperature on Sundays should depend on the region. The AI mixed two concepts that do not
belong together. A person can discard that after a moment of thinking, but only if they stop to think, and I could
easily have taken it.

**What I take with me.** If I worked with AI again, I would start with a file of rules for the project that it must
always follow. Mine would be: check its own figures (for example with a screenshot) before saying they are done, so
my feedback goes to the content and not to overlapping labels; do not agree with me just because I said something,
but be objective and question my ideas; run a small test before every long run, but never conclude from it; and stay
on one path at a time, mentioning a side idea only when it really matters, because too many ideas at once distract me
from the analysis. I would also keep AI-written documents short. Some files in our repo repeat the same information
in many places. In Phase II, without AI, I will miss how quickly
it produced a working first version of a visualization or the dashboard, even if it needed a lot of feedback
afterwards. On the other hand, I expect my analysis to be easier to trust: I will build it on papers I read myself,
instead of questioning every claim of the AI or not having the time to check all the papers it cites.
## Together

### What we agree on

<!-- Proposal by Sandro. Carlos: please change, replace or delete anything you do not agree with. -->

The AI was fast at building and slow to be right. It gave us first versions of code,
experiments and the dashboard quickly. The first number or explanation was often
plausible and wrong (304 instead of 306 start times, "this warming is in every case"),
so we treated it as a hypothesis until we had checked it in the data.

Small tests mislead. A 12-point smoke test and a 6-case test each suggested something
that did not hold on thousands of cases. We run a small test before a long run, but we
do not conclude from it.

The questions and the decisions stayed ours: what to investigate, which figures to
keep, and what goes into the repository. The AI proposed options, and we accepted,
changed or rejected them.
