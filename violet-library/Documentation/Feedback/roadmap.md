# Public feedback loop: build sequence

**Status:** Planning only; these milestones have not started. [Design and decisions](design.md).

| Order | Deliverable | Completion check |
| --- | --- | --- |
| 1 | Freeze the feedback wording, values, privacy notice, retention rule, and versioned search-snapshot contract. | A reviewer can tell exactly what a visitor sends and what is retained. |
| 2 | Set up a private free-tier feedback API and database with separate maintainer access and no credential in the browser or Git. | Test submissions can be inserted and read only by maintainers; invalid and duplicate submissions are rejected or deduplicated. |
| 3 | Add accessible per-book ratings and a whole-list none-fit action to the existing five-first, ten-maximum UI. | A visitor can rate, correct, and receive confirmation by keyboard or pointer; search continues if feedback is down. |
| 4 | Add bot protection, rate limits, input limits, failure handling, deletion receipt, and raw-data retention. | Abuse and quota tests fail safely; a receipt removes its submission; no raw query appears in public artifacts or logs. |
| 5 | Build a private weekly review/export workflow aligned with the existing 0/1/2 human rubric. | Maintainers can distinguish sample coverage, metadata, level, language, and ranking problems; public votes remain separate from human grades. |
| 6 | Run a controlled ranking or catalog improvement experiment and a frozen human evaluation. | Versioned report compares the same questions and catalog; at least 41/50 clearly useful first-five searches is required for the existing target, with no material subgroup regression. |
| 7 | Deploy and monitor the feedback feature, document rollback and quota behavior, and update README and handover. | A real public submission succeeds end to end; the previous search release remains recoverable. |

Build milestone 1 as a reviewable specification before writing application code. Do not publish feedback controls that merely appear to save data. The API/database account and its access model are a concrete setup dependency for milestones 2–7. The free service may stop writes at a quota; it must not silently lose ratings or interrupt book search.
