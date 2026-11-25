# Feedback design record

## 2026-11-19 — `design-public-feedback-loop`

1. Reviewed the current GitHub Pages browser demo, existing human-review rubric, 1,884-book sample limitations, and the unmet more-than-40/50 relevance target.
2. Proposed explicit per-book ratings and a whole-list none-fit signal. The user chose **any visitor** rather than invited testers for the first release.
3. Kept feedback private and separate from public Git, and retained the decision that no real NYU login or profile is part of the prototype.
4. Chose a replaceable feedback API/private database boundary because static GitHub Pages cannot receive submissions. Cloudflare Worker plus D1 is the free pilot candidate, not a deployment decision or a guarantee of production capacity.
5. Required human review and frozen evaluation before any feedback-derived ranking or model change. Public anonymous ratings are diagnostic signals, not verified student labels.
6. Wrote [the proposed design](design.md) and [build sequence](roadmap.md). No application or infrastructure code was changed, and no feedback is currently collected.

## 2026-11-19 — `add-public-feedback-loop`

1. Built `feedback-api/` as a separate Sites Worker with a private D1 database. Its schema stores each rating, an audit event, and a daily rate counter. Generated the known-book allowlist from the checksum-verified 1,884-book frontend catalog so arbitrary book IDs are rejected.
2. Added strict payload validation, exact Pages-origin CORS, a 4 KB body cap, 20-submission daily per-IP limit, retry deduplication, correction and deletion receipts, and 90-day retention cleanup. The secret rate key is in Sites runtime configuration, not Git. The API has no public feedback-read route.
3. Added browser controls for each book and for “none fit,” optional fixed reasons, a submission notice, save status, correction, deletion, and retryable error messages. Search and model ranking still happen only in the browser; feedback does not update ranking automatically.
4. Added API contract and migration tests plus frontend payload tests. Locally verified 10 API tests, 10 frontend tests, the frontend production build, and the Worker artifact build. A live API smoke request returned 201 and its deletion returned 204; the health endpoint returned 200.
5. Published the Worker as a public Site so any visitor can submit, while its D1 database remains private. Added the public API URL to the Pages build and a nightly retention workflow. Public anonymous feedback has no bot challenge and remains low-trust until reviewed.
6. The first Pages run on the feature branch was rejected before build steps by the GitHub Pages environment branch rule. Fast-forwarded the reviewed commit to the existing `build-nyu-search-demo` deployment branch. [The final Pages run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/44640736059) passed.
7. In the live browser, searched for ocean plastic pollution with E5 small, saw ten ranked books and per-book/whole-list controls, submitted a rating, corrected it, and confirmed its saved state remained after “More options.” The earlier API smoke request returned 201 and its deletion returned 204. One browser-generated synthetic rating remains in private storage and should be ignored during analysis.
8. Added the daily retention workflow to the default `main` branch in a separate commit so GitHub's scheduler can run it without merging older research branches into `main`. [Manual verification run 44641246291](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/44641246291) passed. Updated the root README, handover, design, and runbook.
