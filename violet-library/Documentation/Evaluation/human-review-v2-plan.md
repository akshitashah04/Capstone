# V2 human review implementation plan

**Goal:** Freeze human-review packets for the newer DOAB and textbook results, track genuine ratings, and score only complete packets.

**Architecture:** Read the two committed compact ZIP artifacts in memory, validate them against their manifests and the unchanged 50-question file, and emit separate rank-blind CSV sheets with signed metadata. A small local/CI command checks edits; a scorer joins completed grades back to the frozen ranks.

**Tech stack:** Python 3.11 standard library, pytest, GitHub Actions.

## Constraints

- No full dataset or model download on a laptop.
- No assistant-created human grades or reuse of v1 human-review sheets.
- No personal student information, paid service, or external search selection.
- Every source input, index revision, and evaluation limit remains traceable.

## Work

1. Add tests for checksum rejection, candidate completeness, rank blindness, grade validation, and scoring blocked on unfinished sheets.
2. Build the packet generator and progress/scoring command from the frozen artifacts.
3. Generate both packets, verify all 50 + 19 sheets, and document clear reviewer instructions.
4. Add a lightweight workflow for every review-file change and update the repository guide and handover.
5. Confirm local tests, lint, generated packet counts, and GitHub checks; push a purpose-named branch.

The actual ratings and later independent holdout cannot be completed by code or inferred from the earlier assistant labels. They require reviewers and anonymous questions from intended users.
