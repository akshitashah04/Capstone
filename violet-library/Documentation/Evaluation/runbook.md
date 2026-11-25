# Search evaluation runbook

## Run the pilot

1. Open the repository's **Actions** tab and select **Collect and score owned search evaluation**.
2. Select **Run workflow** on `main`. The workflow also runs when evaluation code or questions reach `main`.
3. The job downloads the pinned published index and model to a temporary GitHub runner. It uses our `SearchEngine` for all three ranking modes. No full index is downloaded to a teammate's laptop.
4. Open the completed job's **Summary** for the top examples and complete review pool. The **search-evaluation-pilot** artifact contains `runs.csv`, `timings.csv`, `review.csv`, `manifest.json`, and `summary.md`; GitHub retains it for 30 days.

The job needs no Hugging Face token because the published dataset and model are public. It uses free GitHub Actions capacity, subject to the repository's available quota. The large index is discarded when the job ends. The first pilot's 12 compact review sheets are now saved in GitHub, so grading does not depend on the artifact's 30-day retention.

## Judge the results

Open [the pilot review folder](../../evaluation/review/pilot/README.md) in GitHub and choose a question file. Each row is one question–book pair returned by at least one mode. The files hide search ranks and sort books by ID to reduce ranking bias. Read the title, abstract preview, and source page before assigning:

| Grade | Meaning |
| --- | --- |
| `0` | Does not answer the question |
| `1` | Partly useful or related |
| `2` | Clearly useful for the question |

Leave `relevance` blank when unsure and resolve it with another reviewer; a blank row cannot be scored. Change only the final grade column. Keep names, email addresses, and real student details out of questions and judgments. The 12 small files are the shared online source; the full catalog and index stay remote.

In the first pilot, 37 of 233 rows have no abstract preview. Open their source links and judge from the available book description or contents; leave the grade blank if the evidence is insufficient.

Commit each question file on a purpose-named branch and merge it into `main` after **Check human review progress** passes. That lightweight job counts grades without downloading the index. When it reaches 233 of 233, manually start **Collect and score owned search evaluation** on `main`. The job recollects the pinned candidates and checks that they match the review sheets even if grades are still blank. It assembles a temporary judgment file and writes `metrics.json` only after all grades are valid. If the question file, index, or ranking code changes the candidate pool, start a new review version. A stopped score step means inputs changed or labels are invalid, not that a search mode scored zero.

## Read the report

`success_at_5` means a clearly useful book appeared in the first five. `pooled_ndcg_at_10` measures ordering within books the three modes retrieved. `known_title_top_1` checks the expected ID for known-title questions. `latency_p95_ms` is the slow end of warm search times on the GitHub runner. Breakdown counts are important because the 12-question pilot is too small for broad claims.

`rank_score` and semantic similarity are relative signals, not confidence percentages. A book missing from the 91,667-book export is a corpus coverage issue; it cannot be fixed by reranking the returned books. Expand to 100–150 anonymous natural questions and complete human judgments before assessing the provisional project targets.

## Repeat the answer-derived diagnostic

1. Read the [diagnostic design](answer-derived-design.md) and [results](answer-derived-results.md). The 24 questions were written from known books and are a development check, not a student sample.
2. Open **Actions → Diagnose answer-derived book retrieval → Run workflow** on `main`. It runs the pinned index on temporary GitHub storage and uploads the small `answer-derived-diagnostic` artifact for 30 days.
3. Read the run summary for top-level target recovery and the artifact's `target-metrics.json` for every source-book rank. A blank rank means that book was outside the top ten for that mode; another returned book may still answer the question.
4. If the question file, source-book mapping, index revision, or ranking logic changes, record the new revision and rerun all modes. Keep the old metrics for comparison instead of overwriting a result without its provenance.

The separate `evaluation/ai-review/pilot-grades.csv` gives the assistant's 233 metadata-based grades. `evaluation/ai-review/pilot-metrics.json` holds their scored pilot results. These files must never be copied into the human review folder or called human judgments. The saved [book-recovery metrics](../../evaluation/diagnostics/answer-derived-metrics.json) belong to the [2026-11-15 cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43775201104); its manifest records the exact question and index revisions. The full catalog and index stay off team laptops.

## Repeat the 50-persona study

The [50 fictional profiles](../../evaluation/personas/README.md), [design](persona-design.md), and [results](persona-results.md) belong to a separate development study. To run its search again, open **Actions → Evaluate 50 synthetic student searches → Run workflow** on `main`. The job checks that the profile file exports exactly to the frozen query file, uses the pinned index on a temporary runner, and uploads ranked results, warm timings, a metadata review pool, and a manifest. It does not score until a complete top-five label file exists for that exact candidate pool.

To reproduce the saved scores from the small ZIP in Git, extract it to a temporary directory and run:

```bash
mkdir -p /tmp/libraries-persona-run
unzip -q evaluation/personas/search-run-99e564e.zip -d /tmp/libraries-persona-run
python -m libraries_evaluation.persona_score \
  --personas evaluation/personas/student-personas.jsonl \
  --queries evaluation/queries/student-personas.jsonl \
  --run-dir /tmp/libraries-persona-run \
  --labels evaluation/personas/ai-labels.csv \
  --output /tmp/libraries-persona-metrics.json
cmp /tmp/libraries-persona-metrics.json evaluation/personas/persona-metrics.json
```

The scorer checks the question hash, artifact checksums, and that every book shown in any mode's top five has one valid grade. `topic_grade=2` means the subject fits; `level_fit` records whether the preview supports the requested audience; `overall_grade=2` requires both. Only the top-five union is judged, so this study measures nDCG@5 and cannot answer the project's nDCG@10 target. Do not use these assistant grades as human review or assume a short abstract proves a book is readable. Delete the temporary extraction when done; it does not include the full catalog or index.

## Change or rerun

Edit `evaluation/queries/pilot.jsonl` only when intentionally changing the pilot. Keep stable IDs for unchanged questions. Run local synthetic tests with `python -m pytest -q` and `ruff check .`; the real-index command refuses to run outside GitHub Actions. Read [the design](design.md) and [review handoff design](review-design.md) before altering metric definitions or grading files, and record each change in [the session log](session-log.md) and root README.
