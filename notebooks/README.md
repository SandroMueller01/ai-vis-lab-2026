# Notebooks: how the human–AI collaboration led to our results

Four notebooks that replay the key steps of building this repo with a generative AI assistant
(Pair 1, AI-aided in Phase I). Each step has an *AI collaboration* box (prompt, AI proposal, human
check, decision), followed by code that re-computes the evidence from the repo.

| Notebook | Content | Needs |
|---|---|---|
| `00_ai_collaboration_overview.ipynb` | Timeline of PRs, AI verdict per PR, accepted / modified / rejected suggestions | git history |
| `01_smoke_test_and_covariates.ipynb` | Why extra input does not help TiRex-2, and how a flat result changed the plan (PR #8) | dashboard data; TiRex-2 optional |
| `02_event_labels_and_cold_fronts.ipynb` | Cold-wave days (any hour vs same hour), gap filling, cold drop vs cold front, front checks (PRs #9, #11) | `data/austria_15km` |
| `03_phase1_results.ipynb` | Forecast design (306 + 30 runs), Q1–Q5 evidence, the jump-to correction (PRs #13, #14) | `data/austria_15km`, dashboard data |

Prompts are reconstructed from the PR descriptions, not verbatim. The full log is in
[`../ai-interactions/phase1-ai-aided-pair.md`](../ai-interactions/phase1-ai-aided-pair.md).

Run them in the container (outputs are kept on purpose, for the figures):

```bash
gh release download data-austria-15km --dir data && tar -xf data/austria_15km.tar -C data
docker compose up        # JupyterLab on http://localhost:8888, open notebooks/
```

The live re-run of the synthetic covariate check in notebook 01 needs TiRex-2 and its weights (in the
Docker image). Without them the cell is skipped and the recorded numbers from PR #8 are shown.
