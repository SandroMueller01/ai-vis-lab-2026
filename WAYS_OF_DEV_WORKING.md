# Ways of dev working

Short version: **nothing goes to `main` directly.** Every change is a branch →
pull request → one review → merge.

## 1. Branch

```bash
git switch main && git pull
git switch -c <prefix>/<short-name>
```

| Branch prefix | For | Example |
|---|---|---|
| `data/` | data acquisition, preprocessing | `data/event-labels` |
| `p1/` | Phase I analysis (model behaviour) | `p1/pair2-calibration-plots` |
| `p2/` | Phase II analysis (model internals) | `p2/pair1-gate-heatmaps` |
| `infra/` | Docker, CI, repo setup | `infra/docker-devcontainer` |
| `docs/` | READMEs, AI logs, comparison write-ups, submission material | `docs/phase1-comparison` |
| `fix/` | fixing something that's broken on `main` | `fix/tyrol-label-timezone` |

Use lowercase and hyphens. Keep branches small and short-lived. Several small
PRs a week are much easier to review than one huge PR the night before a
deadline.

## 2. Commit

Every commit message starts with a **prefix**, then a short summary in the
imperative ("add", not "added"):

```
<prefix>: <what changed>

<optional body: why, and anything a reviewer should know>
```

| Commit prefix | Use for | Example |
|---|---|---|
| `data:` | acquisition / preprocessing code, dataset docs | `data: add shared event labels for cold drops` |
| `feat:` | new analysis code, plots, notebooks | `feat: add quantile calibration plot per region` |
| `fix:` | bug fixes | `fix: align station hours to INCA analysis time` |
| `refactor:` | restructuring without changing results | `refactor: move plotting helpers into utils` |
| `docs:` | READMEs, AI logs, write-ups | `docs: log Phase I prompts for pair 1` |
| `infra:` | Docker, dependencies, dev container | `infra: pin tirex-2 to 0.3.1` |
| `ci:` | GitHub Actions workflows | `ci: add PR description check` |
| `chore:` | small housekeeping (gitignore, renames) | `chore: ignore HF cache` |

Rules of thumb:
- One logical change per commit. Don't mix "new plot" with "fix the loader".
- Summary line ≤ 72 characters, no full stop at the end.
- Never `stuff`, `wip`, `fix` on their own. Say *what* was fixed.

## 3. Open a pull request

Push the branch and open a PR on GitHub. The description is pre-filled from
[`.github/pull_request_template.md`](.github/pull_request_template.md). Fill in
every section. The **PR description** check stays red until the Summary is
written and every checklist box is ticked. If an item doesn't apply, tick it
and add `(n/a: reason)`.

The **PR title** follows the same prefix scheme as commits, e.g.
`data: add shared event labels for cold drops and thunderstorms`. With squash-merge it becomes the
commit on `main`.

Open the PR as a **draft** early if you want feedback before it's done.

## 4. Review

- **Who:** at least **one** teammate approves. By default, ask someone from the
  *other* pair, so both pairs know what's in the repo. But in a phase where the
  pairs work independently (AI-aided vs. human-only), **don't look at the other
  pair's analysis until the comparison step**. Get those PRs reviewed by your
  own pair partner instead.
- **What to check:**
  - Does it run? Pull the branch and run the "How to reproduce" commands in the container.
  - Are the conclusions supported by the figures and numbers shown, or are they over-claimed?
  - Is the AI usage section honest and complete? We need this for the AI4Vis part of the grade.
  - Is anything big or private committed (data, weights, tokens)?
- **How:** comment on specific lines. Use GitHub's *Suggest changes* for small
  fixes. Prefix comments that must be fixed before merge with **`blocking:`**;
  everything else is optional (`nit:`, `question:`).
- **Turnaround:** review within **48 h**, and faster in deadline weeks.

## 5. Merge

When CI is green and the PR is approved, the **author** merges with **Squash and
merge** and deletes the branch. Each PR then becomes one commit on `main`.

## Environment

Everyone uses the Docker image, so "works on my machine" means the same thing
for all of us. See [README → Setup](README.md#setup).
