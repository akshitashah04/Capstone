# Public feedback implementation plan

**Approved direction:** Any visitor may send structured feedback without login. Search stays on GitHub Pages; a separate Cloudflare Worker with private D1 storage receives ratings. No rating changes live ranking automatically.

## Files and responsibilities

| Path | Responsibility |
| --- | --- |
| `feedback-api/worker/index.js` | HTTPS API routes, CORS, rate limiting, D1 writes, correction, deletion, retention cleanup |
| `feedback-api/worker/validation.js` | Pure request validation and accepted rating values |
| `feedback-api/worker/known-books.js` | Versioned allowlist of demo book IDs generated from the published sample |
| `feedback-api/drizzle/` | Append-only D1 schema migration and metadata |
| `feedback-api/test/` | Validation and API tests with synthetic records |
| `frontend/src/feedback/` | Client request contract and accessible rating controls |
| `frontend/src/main.ts`, `frontend/index.html`, `frontend/src/style.css` | Attach feedback to results and explain what is submitted |
| `.github/workflows/deploy-demo-pages.yml` | Build and publish the fast-forwarded Pages branch after tests pass |
| `Documentation/Feedback/`, `README.md`, `Documentation/HANDOVER.md` | Setup, privacy, operations, checks, and handoff |

## Build order and gates

1. Write failing validation tests for allowed ratings, reason codes, query length, catalog checksum, book ID membership, unique displayed positions, and a whole-list none-fit rating. Implement only the accepted contract.
2. Write failing API tests for successful submission, duplicate idempotency, correction with a receipt, deletion with a receipt, rejected origins and malformed requests, and quota failure. Add the D1 schema and Worker routes.
3. Write failing frontend tests for its request payload and result association. Add card controls and the whole-list control with an explicit privacy notice, retry/error state, and correction/deletion actions.
4. Build and validate both projects. Deploy the Worker and database first; verify a real public write and owner-only database schema. Then fast-forward `build-nyu-search-demo` to the reviewed `add-public-feedback-loop` commit and deploy the frontend to the existing Pages URL.
5. Verify a real browser search, rating, correction, deletion, keyboard flow, and search continuity when the API is unavailable. Update the runbook with exact deployment IDs and operational limits.

**Release gate:** No feedback control appears on the live site unless a public submission reaches private storage and can be corrected/deleted. Raw visitor queries must not enter public Git, Pages assets, or CI logs. The 41/50 relevance target remains a later human-evaluation gate, not a claim from public votes.
