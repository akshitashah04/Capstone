# Query fit and catalog coverage implementation plan

**Goal:** Reach an evidence-backed collection and ranking improvement ready for later human review and a five-result UI.

**Architecture:** Keep the frozen DOAB source and current index as a baseline. Add repeatable miss and metadata audits, explicit query-needs parsing, and an optional second-stage ranking mode that runs on our own candidate list. Store compact reports and pin all model and source revisions.

**Tech stack:** Python 3.11, SQLite FTS5, NumPy, Sentence Transformers, pytest, GitHub Actions, Hugging Face dataset storage.

## Global constraints

- No full source or index files on a laptop; real-data jobs run on temporary GitHub runners.
- No paid service, real student account, or third-party search selection.
- Original metadata and book links retain source provenance.
- The 50 fictional questions and assistant grades are development diagnostics, not final acceptance data.

## Tasks in the agreed order

1. **Miss review:** Validate the saved artifact and labels; produce a per-query failure category and aggregate counts. Test category boundaries and checksum rejection with synthetic files. Save the report and interpretation.
2. **Metadata audit and repair:** Read the published quality report and add a cloud-only source-field audit for alternate abstracts, alternate titles, and subject coverage. Where a source value exists, expose a grounded description or searchable title without guessing; version any changed index artifact. Test fallback and provenance on synthetic records.
3. **Query understanding:** Parse explicit reading needs into a small stable schema while retaining the complete query. Test positive and negative examples, including multilingual queries and an unspecified need.
4. **Second ranking pass:** Pin a multilingual model and score only a bounded candidate pool. Add a mode with deterministic tie breaks, relative scores, and a clear failure when the model is missing. Test ranking and bounds with a fake scorer. Run a cloud diagnostic against the frozen 50 questions without changing their labels.
5. **Collection coverage decision:** Compare the miss audit, metadata audit, and new diagnostic. Record which gaps call for retrieval improvements versus a new corpus. Review candidate corpus rights and metadata before any expansion; add a separate ingestion plan if expansion is justified.

## Verification and handoff

Run project tests and lint locally with synthetic fixtures, then a cloud job against the pinned index. Update the README, evaluation documentation, session log, and handover with exact commands, artifact revisions, measured outcomes, limits, and the next UI/deployment boundary. Push a purpose-named branch and merge only after checks pass.

## Execution record

Tasks 1–4 were implemented and tested. Task 5 produced a separate 1,915-book cloud coverage experiment from the unfiltered Open Textbook Library CSV; the supplement was not merged because language, duplicate, and human-fit checks remain. See [the results](query-fit-results.md) for the exact cloud runs and limits. Human ratings and the held-out acceptance retest are the next two steps and were intentionally left untouched at this checkpoint.
