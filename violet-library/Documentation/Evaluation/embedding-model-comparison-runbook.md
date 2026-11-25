# Embedding comparison runbook

## Inputs and scope

This trial compares pinned E5 base and GTE multilingual base on the same 91,667-book DOAB source, v2 keyword database, and 50 authored student questions. The [design and incident record](embedding-model-comparison-plan.md) explain the input conventions and GTE compatibility pin. The current E5 small hybrid result is 17/50 under a separate assistant review. This is a development comparison, not a human acceptance test.

## Cloud run

The [comparison workflow](../../.github/workflows/compare-embedding-models.yml) ran on the purpose branch. Its successful recovery version reused four verified E5 base shards from [run 43848201040](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43848201040) and built eight smaller GTE shards. Each model was assembled against the pinned v2 book database and tested on every question in semantic and hybrid modes. It did not publish a full experimental index. The public pinned source and models required no `HF_TOKEN` for this read-only trial. The E5 shard artifacts expire after one day: this workflow is a record of the completed recovery run, and manual reruns after those artifacts expire will fail. A future fresh comparison must build new E5 shards and remove the fixed cross-run artifact dependency before dispatch.

Each job stores the source, model, and full index only under GitHub's temporary runner directory and removes them at the end. Temporary vector-shard artifacts expire after one day. The two compact result artifacts contain only `runs.csv` and `manifest.json` and expire after 30 days. Save those two small artifacts in `evaluation/model-comparison/` after validating their checksums; do not commit vector shards, model files, or the full catalog.

The first attempted run failed because Transformers 5 corrupted GTE's position buffer. The corrected run then hit the four-hour limit on GTE while E5 finished. Use only successfully completed evaluation artifacts with full validated shards. The workflow installs Transformers 4.57.6 for both models, and the loader refuses GTE under version 5 or later.

## Relevance review and scores

For each model, pool the first five semantic and hybrid results by question and book ID. The [trial scorer](../../src/libraries_evaluation/embedding_trial_score.py) requires one separate assistant label per pooled pair and validates the frozen query checksum, result checksum, rankings, and model revision. Reuse a prior assistant judgment only for the same question and book; inspect every new pair without looking at its rank. A clear fit requires the subject, stated practical need, reading level, and usable language. An uncertain or partial fit is `0` under this strict binary diagnostic. Keep all human-review sheets blank.

After labels are complete, run from the repository root:

```bash
python -m libraries_evaluation.embedding_trial_score \
  --queries evaluation/queries/student-personas.jsonl \
  --results-dir evaluation/model-comparison/e5-base \
  --labels evaluation/model-comparison/e5-base-labels.csv \
  --model e5-base \
  --output evaluation/model-comparison/e5-base-metrics.json

python -m libraries_evaluation.embedding_trial_score \
  --queries evaluation/queries/student-personas.jsonl \
  --results-dir evaluation/model-comparison/gte-base \
  --labels evaluation/model-comparison/gte-base-labels.csv \
  --model gte-base \
  --output evaluation/model-comparison/gte-base-metrics.json
```

Compare first-five success with the E5 small hybrid baseline of 17/50, then compare first-result success, strong precision at five, and runner warm p95. Record every new book pair and remaining misses. These 50 questions are authored development cases; no model passes for student use without natural questions and human ratings.
