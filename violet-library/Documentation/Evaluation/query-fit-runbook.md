# Query fit audit runbook

## Reproduce the local, small-file audit

Use the project virtual environment. This command reads only the committed 605 KB frozen-result ZIP and labels; it does not download a catalog or index:

```bash
.venv/bin/python -m libraries_evaluation.miss_audit \
  --run-zip evaluation/personas/search-run-99e564e.zip \
  --labels evaluation/personas/ai-labels.csv \
  --queries evaluation/queries/student-personas.jsonl \
  --output evaluation/personas/miss-audit.json
```

Check the Python tests and lint with `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check .`.

## Cloud-only source and index jobs

Run the workflows from GitHub Actions on the purpose-named branch. The `HF_TOKEN` repository secret is used only by the index publisher. Do not copy that token into a local file or shell history.

1. **Audit pinned book metadata:** `.github/workflows/audit-book-metadata.yml` downloads the pinned 117 MB Parquet source to temporary runner storage and uploads only a small JSON report.
2. **Upgrade book index:** `.github/workflows/upgrade-search-index.yml` checks the pinned v1 index and source, copies unchanged vectors, rebuilds a richer SQLite database, verifies the v2 bundle, and publishes `search/v2` beside `search/v1`. It deletes temporary files even after failure.
3. **Compare the second ranking pass:** `.github/workflows/diagnose-reranked-search.yml` loads the pinned v2 index and models, runs all four modes on the same 50 questions, and uploads an unjudged result artifact. Its result ZIP is checked into `evaluation/query-fit/` for long-term reproducibility.
4. **Check textbook coverage:** `.github/workflows/audit-textbook-coverage.yml` downloads the full, unfiltered Open Textbook Library CSV, builds a temporary project-owned index, searches the 19 topic misses, and uploads only a small quality report and 95 candidate rows. The raw CSV and temporary index are removed.

The pinned v2 DOAB commit is `b745902168aca10589fd0b376b58eb8019291b37`. The earlier v1 index remains pinned at `f54ded49b97a92ca8e5dce0463500043ea2a19a4`. Do not silently change a revision in one job without updating its manifest, runbook, and evaluation comparison.

## Interpreting the outputs

`miss-audit.json` classifies only the **judged** first-five pool. `field-audit.json` counts source-provided alternatives. `reranked-run.zip` contains query-needs JSON and a four-mode ranked CSV; new book pairs have no relevance grade. `otl-coverage-run.zip` contains the exact source CSV checksum and candidate links, but no human grade. Ranking scores in either run are not probabilities. An absent description means there is too little source evidence for a reliable two-to-three-line summary.

Human reviewers should use the existing evaluation guidance, judge topic and reading-level fit separately, and leave unknowns unknown. Do not train on the final held-out questions. A later UI should show five unique books first and at most ten after “More options,” with a grounded description and source link. A free deployment must provide an interactive process that can read the remote index; the current GitHub Actions jobs are batch jobs and GitHub Pages is static hosting.

The existing 233-pair human-review sheets and `src/libraries_evaluation/config.py` are intentionally pinned to **v1**. Do not change that pin or reuse those sheet IDs as if they rated v2 search. The next human-review phase needs a separately frozen v2 candidate collection and its own sheets before any v2 quality claim.

Before building the public demo, verify a zero-cost interactive runtime against its current provider terms and this index's memory/startup needs. GitHub Pages is suitable for static UI files only. Current [Hugging Face Spaces rules](https://huggingface.co/docs/hub/spaces-overview) gate new Gradio/Docker compute Spaces behind a paid plan except eligible free ZeroGPU; [Render's free instance](https://render.com/docs/compute-plans) has 512 MB RAM. Neither is yet verified to host this full Python search service at zero cost.
