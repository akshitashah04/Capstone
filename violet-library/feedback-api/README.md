# Feedback service

This Cloudflare Worker stores voluntary feedback from the public Violet Library demo in a private D1 database. It never searches or ranks books. The GitHub Pages browser app remains the search interface.

## Interface

| Request | Purpose |
| --- | --- |
| `POST /v1/feedback` | Save one book rating or a whole-list `none_fit` report. Returns a correction/deletion receipt. |
| `PUT /v1/feedback/{id}` | Correct a book rating using `X-Feedback-Receipt`. |
| `DELETE /v1/feedback/{id}` | Delete a visitor's submission using the receipt. |
| `GET /health` | Check database availability and remove feedback older than 90 days. |

The API allows browser writes from `https://akshitashah04.github.io`. It validates book IDs against either the original DOAB sample or the combined demo catalog using the submitted catalog checksum. It limits request size, validates every field, deduplicates retries, and caps submissions at 20 per IP per UTC day by default. The IP is used to create a secret-keyed daily hash; the raw IP is not stored in the application database. `RATE_PEPPER` is stored as a secret in Sites runtime configuration, never in Git.

Anonymous ratings are unverified signals. This release has no bot challenge or automatic model updates. Any ranking change requires human review and an independent evaluation. The service has no public read or export endpoint.

## Files

| Path | Purpose |
| --- | --- |
| `worker/index.js` | Routes, CORS, rate limits, receipt checks, D1 writes, retention cleanup. |
| `worker/validation.js` | Strict request validation. |
| `worker/known-books.js` | Generated allowlist and catalog checksum; commit with the matching frontend catalog. |
| `drizzle/` | Immutable hosted database migration and journal. |
| `scripts/sync-catalog.mjs` | Regenerates the allowlist from the checked frontend manifest. |
| `scripts/build.sh` | Copies only deployable Worker modules, manifest, and migrations. |
| `scripts/validate-artifact.mjs` | Checks the deployable module. |
| `test/` | Unit and in-memory D1 contract tests. |
| `.openai/hosting.json` | Sites identity and private D1 binding; contains no credential. |

## Local verification

Use Node 22 or newer:

```sh
node scripts/sync-catalog.mjs
npm test
bash scripts/build.sh
node scripts/validate-artifact.mjs
```

If the frontend catalog changes, regenerate `known-books.js`, verify the checksum and both test suites, then deploy the service before the new Pages UI. The generated allowlist includes the current combined catalog and its base DOAB catalog. See the [feedback runbook](../Documentation/Feedback/runbook.md) for the private ranking evaluation.

## Publishing and operations

The service is published through the connected Sites project identified in `.openai/hosting.json`. The source helper pushes this folder to that Site's separate source repository, packages `dist/`, and Sites saves and deploys that exact source revision. The GitHub repository remains the team-owned source of record. On first setup, create a secret runtime variable named `RATE_PEPPER` and mark the Site public so any visitor can submit. Do not put the secret in GitHub Actions or a source file. The Pages workflow sets the public API URL during its build.

The nightly GitHub workflow calls `/health` to enforce the 90-day raw-data limit even when no one submits. Check the action and Sites deployment status after a release. A failed feedback service must not block book search; the browser reports a retryable feedback error. Database access is limited to Site owners/editors. Export only reviewed, minimized records for evaluation; never commit raw visitor questions or ratings.
