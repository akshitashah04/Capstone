# Feedback release and review runbook

## What visitors see

The public [Violet Library demo](https://veedantbrahmbhatt.github.io/Libraries/) searches 1,891 open-access books in the visitor's browser. Under each recommendation, a visitor can choose Useful, Somewhat useful, or Not useful; a fixed reason is optional. A separate control says none of the shown books fit. The page explains what a submission sends. Searching, opening a link, or changing the model does not send feedback. A saved rating can be changed or deleted while the page stays open. There is no login or personal profile.

## What the service stores

Each submission stores the query, shown book IDs and positions, one rating and optional reason, model and mode, release ID, catalog checksum, timestamps, and a daily keyed IP hash for abuse limits. It does not store raw IP, NYU email, or a persistent visitor ID. The receipt remains in the visitor's browser memory. The private D1 database is attached to the [Sites feedback service](https://violet-library-feedback.fabled-tetra-1279.chatgpt.site/health); the public API has no read endpoint. Raw feedback expires after 90 days when `/health` runs. The scheduled [retention workflow](../../.github/workflows/feedback-retention.yml) calls that endpoint daily.

## Release order

1. If the catalog changes, run `node feedback-api/scripts/sync-catalog.mjs` and commit the generated allowlist with the new frontend manifest.
2. Run `node --test feedback-api/test/*.test.js`, `npm test --prefix frontend`, `npm run build --prefix frontend`, `bash feedback-api/scripts/build.sh`, and `node feedback-api/scripts/validate-artifact.mjs` using Node 22 or later.
3. Publish `feedback-api/` through the Sites source helper, save its pushed commit and archive as a Site version, and deploy it. Confirm `/health` returns 200 and a synthetic submission can be deleted.
4. Push the purpose branch to GitHub, then fast-forward `build-nyu-search-demo` to that reviewed commit. The Pages workflow builds with the feedback API URL and Git commit as release ID. Confirm its run succeeds and the public page shows feedback controls after a search. The Pages environment permits its deployment branch, not arbitrary feature branches.
5. Keep the retention workflow on the repository's default `main` branch so GitHub schedules it. Run it manually once after deployment and check its status. Keep the Sites secret `RATE_PEPPER` outside Git and GitHub Actions.

If the API is down, book search still works and visitors see a retry message when they try to send feedback. Publish the updated service before Pages. The service accepts the original DOAB catalog checksum with its original IDs and the combined catalog checksum with both sets of IDs.

## Weekly review

1. In Sites, allow only named project maintainers to view private D1 rows. Export the minimum fields needed into a private review environment; do not commit raw visitor queries or ratings.
2. Group reports by topic, language, reading level, broken links, and `none_fit`. Inspect duplicates and implausible patterns; anonymous votes are not verified student labels.
3. Check whether a suitable book exists in the **demo sample** before blaming ranking. Fix missing metadata or sample coverage with a versioned data change.
4. Have reviewers judge a selected set of question–book pairs using the established 0/1/2 rubric. Keep those human judgments separate from anonymous feedback.
5. Test proposed ranking or model changes against a frozen independent question set. The current target is at least 41/50 questions with a clearly suitable top-five book; no release has met this target yet.
6. Release a change only after measured improvement and regression review. Keep its catalog, model, code revision, and evaluation record together for rollback.

## Test ranking changes with reviewed feedback

Use a maintainer-only export of the current feedback rows. Export the following fields from the private database and keep the result outside the checkout. The current rows reflect visitors’ edits and deletions.

```sql
SELECT query_text, results_json, target_book_id, rating, reason,
       model_key, search_mode, release_id, catalog_sha
FROM feedback
ORDER BY created_at, id;
```

```sh
node feedback-api/scripts/prepare-ranking-review.mjs /private/export.json /private/review.json
```

The script accepts a JSON row array or a D1 JSON result containing one `results` array. It groups reports by normalized question and keeps the display position, release, model, and catalog for each per-book rating. It counts whole-list reports separately. A `none_fit` count is a prompt to inspect coverage and may justify writing a new evaluation question. Anonymous votes can suggest which topics and books to review. They never supply grades automatically.

Prepare a private JSON array with entries such as `{"id":"dev-01","query":"A reviewed question","split":"development"}`. Use reviewed and de-identified questions inspired by reports for development. Add independently sourced questions with `"split":"holdout"`. The scorer rejects duplicate normalized questions. Include Chinese and Hindi queries and check them separately before release.

```sh
node frontend/scripts/review-ranking.mjs pool /private/questions.json /private/pool.json
node frontend/scripts/review-ranking.mjs score /private/pool.json /private/metrics.json
```

The pool command downloads the pinned browser GTE model and captures the top five for the same catalog under keyword weights 0.5, 1, 1.5 and 2. Weight 1 is the deployed baseline. For blind review, give reviewers only the question IDs, question texts, and sorted books under `grades`. Fill every blank with a human grade using the existing 0 (unhelpful), 1 (partially useful), or 2 (clearly useful) rubric. Run `score` on the completed pool. It chooses a weight using development labels alone, then reports clear top-five fits and NDCG@5 for that choice and the baseline on holdout.

A passing report requires at least 50 holdout questions, clear top-five fit on at least 82%, more clear fits than the baseline, and no drop in NDCG@5. The report makes no deployment changes. Review query-level and language regressions before approving a weight for release. Keep raw feedback, question-level packets, and credentials out of Git and public deployment artifacts.
