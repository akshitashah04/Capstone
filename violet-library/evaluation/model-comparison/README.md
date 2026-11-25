# Model comparison evidence

This folder contains compact search results and assistant judgments from the controlled [E5 base and GTE trial](../../Documentation/Evaluation/embedding-model-comparison-results.md). The full book list, model weights, and search vectors are not stored here.

| File | Purpose |
| --- | --- |
| `e5-base/manifest.json` | Pinned model, source, query, and result checksums from the cloud run. |
| `e5-base/runs.csv` | First ten E5 base books for each of 50 queries in meaning-only and combined search, with rank and runner timing. |
| `e5-base-labels.csv` | One strict assistant relevance judgment per distinct query–book pair in the first five; 222 prior identical-pair judgments carried, 191 new pairs inspected. |
| `e5-base-metrics.json` | Recomputed E5 base quality and timing figures from the checked run and labels. |
| `gte-base/manifest.json` | Pinned GTE model, source, query, and result checksums from the successful cloud run. |
| `gte-base/runs.csv` | First ten GTE books for each of 50 queries in meaning-only and combined search, with rank and runner timing. |
| `gte-base-labels.csv` | One strict assistant relevance judgment per distinct first-five question–book pair; 224 identical-pair judgments carried and 191 new pairs inspected. |
| `gte-base-metrics.json` | Recomputed GTE quality and timing figures from the checked run and labels. |

The [runbook](../../Documentation/Evaluation/embedding-model-comparison-runbook.md) explains how to reproduce the scoring. Both full-catalog runs completed in [recovery run 43896334769](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43896334769). These are assistant-reviewed development results, not human ratings or calibrated confidence scores.
