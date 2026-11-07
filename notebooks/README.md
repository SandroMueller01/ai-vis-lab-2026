# Notebooks: how the human–AI collaboration led to our results

Shared set-up notebooks of the AI-aided pair (Pair 1, AI-aided in Phase I). Each step has an *AI collaboration*
box (prompt, AI proposal, human check, decision), followed by code that re-computes the evidence from the repo.

The repo was built with a generative AI assistant. Every pull request has an *AI usage* section, and the full log is in
[`../ai-interactions/phase1-ai-aided-pair.md`](../ai-interactions/phase1-ai-aided-pair.md). Prompts in these notebooks
are reconstructed from the PR descriptions, not verbatim; the exact prompts are in that log.

| Notebook | Content | Needs |
|---|---|---|
| `01_smoke_test_and_covariates.ipynb` | Why extra input does not help TiRex-2, and how a flat result changed the plan (PR #8) | dashboard data; TiRex-2 optional |
| `02_event_labels_and_cold_fronts.ipynb` | Cold-wave days (any hour vs same hour), gap filling, cold drop vs cold front, front checks (PRs #9, #11) | `data/austria_15km` |

The notebook about the forecast results and the dashboard (Limits and Errors, and the charts on the *Also tested* page)
is in [`../phase1-model-behavior/pair-1/experiments/phase1_forecast_results.ipynb`](../phase1-model-behavior/pair-1/experiments/phase1_forecast_results.ipynb),
next to the experiment notebooks. The five questions answered there were Sandro's part of Pair 1's Phase I work; Carlos
answered further behaviour questions (history length, repeated patterns, cold fronts, band honesty) in the experiment
notebooks in the same folder.

Run them in the container (outputs are kept on purpose, for the figures):

```bash
gh release download data-austria-15km --dir data && tar -xf data/austria_15km.tar -C data
docker compose up        # JupyterLab on http://localhost:8888, open notebooks/
```

The live re-run of the synthetic covariate check in notebook 01 needs TiRex-2 and its weights (in the
Docker image). Without them the cell is skipped and the recorded numbers from PR #8 are shown.
