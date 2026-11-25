# NYU-inspired search demo implementation plan

**Goal:** Publish a free, responsive, live-query book-search demonstration with model selection and honest sample/score labels.

**Architecture:** GitHub Pages serves a Vite-built browser application plus a compact book sample and three aligned vector files. Browser inference embeds a query; project JavaScript ranks sampled books locally. The built site is a GitHub Actions artifact, so the repository keeps just one copy of the compact sample. The full source and indexes remain on temporary cloud runners or their existing remote repositories.

**Stack:** TypeScript, Vite, Transformers.js/ONNX Runtime Web, Vitest, Python/Numpy for cloud-only sample extraction, GitHub Pages Actions publishing.

## Tasks

1. Add a deterministic cloud-only sampler that validates pinned source/index checksums, unions saved top-ten book IDs, and exports metadata plus half-precision aligned vectors; test its selection and checksum rules with synthetic fixtures.
2. Run the extraction in GitHub Actions while temporary trial shard artifacts still exist; download only the compact result bundle, validate it, and commit under `frontend/public/data/`.
3. Build the accessible NYU-inspired search interface in `frontend/`: query and optional microphone, model/mode controls, loading and error states, five result cards, and “More options” through ten.
4. Implement local vector scoring, keyword scoring, reciprocal-rank fusion, and relative score presentation; test ranking rules, filter/order stability, and empty states with synthetic books.
5. Build to ignored `frontend/dist/`, test desktop and mobile browser behavior, configure GitHub Pages Actions deployment from this purpose branch, and verify the live URL.
6. Update README, UI runbook, session log, and handover with the exact sample size, model downloads, limits, and meeting-demo procedure.

## Quality gates

- The committed sample has no raw full catalog, full vector index, model weight, secret, or student profile.
- Every result link points to the source record and every excerpt comes from source metadata.
- The default model and all explicit model options run against their matching aligned vectors.
- The displayed number is labeled relative relevance, never confidence probability.
- New queries can be entered without selecting a canned prompt; the UI states the sample size.
- The public link loads on GitHub Pages and completes a query after the selected model downloads.
