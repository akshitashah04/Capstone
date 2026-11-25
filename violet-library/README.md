# Violet Library

Violet Library is an independent student project for discovering open-access books. The Pages deployment serves it under [/Capstone/libraries/](https://akshitashah04.github.io/Capstone/libraries/). This copy is based on the collaborative [Libraries project](https://github.com/VeedantBrahmbhatt/Libraries) with the multilingual catalog, semantic search, and student interface changes.

From the repository root, run `npm ci --prefix violet-library/frontend` and `npm run dev --prefix violet-library/frontend`. Open the URL that Vite prints. First-use model downloads are served by Hugging Face.

The feedback service is deployed independently at https://violet-library-capstone-feedback.sound-park-7168.chatgpt.site. Its private D1 database stores submitted ratings, and the Worker allows requests from the Capstone Pages origin. The Pages workflow configures the service URL. The feedback maintenance workflow calls the health endpoint daily to enforce the 90-day retention period.

## Upstream source

Capstone's [libraries-updated branch](https://github.com/akshitashah04/Capstone/tree/libraries-updated) preserves the source and commit history of the updated standalone project. Branches prefixed with [libraries-upstream/](https://github.com/akshitashah04/Capstone/branches/all?query=libraries-upstream) preserve the original upstream commits. The `violet-library/` directory on Capstone's main branch contains the adapted source, tests, documentation, evaluation assets, and upstream workflow definitions.

The Capstone Pages workflow compiles the demo into its deployment artifact and checks that the public route and catalog respond after deployment.

## Relevance score

Semantic search computes cosine similarity between the question and each book's metadata embedding. It displays the resulting score multiplied by 100, with values below 0 or above 100 capped at those bounds. Ranking runs before display rounding. Compare scores within the same search and model.

For a specific U.S. student-visa request, the search expands paraphrases and checks whether catalog metadata actually covers the requested visa or academic-student context. The same check applies in the keyword preview. When the chosen book language has no direct match, the interface reports the coverage gap. Ordinary topics continue to be ranked by the selected language model.

## Full-text student visa collection

The demo indexes six freely readable publications on U.S. student visas, including the EducationUSA undergraduate study booklet, Kit Johnson’s CC BY-SA 4.0 immigration casebook, and four university or college handbooks. The result links open the full publication at the source. The demo stores its catalog metadata and original descriptions. It does not host copies of the publications. Handbooks may contain campus-specific guidance.

## Broader open textbook coverage

The catalog includes 52 OpenStax textbooks across computing, business, economics, social science, humanities, mathematics, science, nursing, and study skills. Book links open the free full-text editions on the publisher’s site, including a Spanish statistics textbook. The collection also includes two additional Chinese books from Project Gutenberg and two Hindi novels from Wikisource. Book descriptions in the demo are original summaries. The browser generates supplemental vectors in small batches and caches them for the current catalog and model revision.

## Semantic relevance audit

The demo always searches by meaning. If the selected language model cannot load, the page asks the visitor to retry or choose another semantic model. GTE Base combines the embedding of the full request (75%) with one that removes request wording (25%). Exact titles, specific visa classes, and identified repair manuals require evidence in the catalog. On broad GTE searches the result list stops at a gap of eight cosine points or more. The gap is a heuristic and is not a calibrated confidence threshold.

The ten-query diagnostic is in [browser-semantic-audit.json](evaluation/queries/browser-semantic-audit.json). The [initial real-model run](https://github.com/akshitashah04/Capstone/actions/runs/45553402496) passed 9 of 10 cases, counting an expected empty result as a pass. The [tuned run](https://github.com/akshitashah04/Capstone/actions/runs/45553612143) passed 10 of 10. It put the target first on eight answerable requests and returned no book for the other two. The focus weight was selected on six labeled cases by summed reciprocal rank. The remaining four cases checked the changes, including the repair-manual regression. This is a small targeted audit, not a general search-quality estimate.

To rerun the diagnostic, install the frontend dependencies and run `node violet-library/frontend/scripts/semantic-audit.mjs`. Private feedback review can use `review-ranking.mjs` to compare semantic focus weights using human grades and an independent holdout. Live ratings do not change the model or ranking on submission.

## Reading access and New York City history

Results distinguish online editions and direct PDFs from catalog records. The direct-full-text filter applies before semantic ranking. The audit checks the Cambridge full-book PDF, OpenStax reading page, and the added NYC editions. General NYC searches require city or borough evidence in the title, subjects, or description. The audit includes “new york city and its history.”

*The Story of Manhattan* and *New York: The Nation’s Metropolis* are bundled public-domain U.S. readings from Project Gutenberg, mirrored in GITenberg. The original edition notices and illustrations are included. Source snapshots are [The Story of Manhattan](https://github.com/GITenberg/The-Story-of-Manhattan_13842/tree/5a2fc0a63249bee387ec59b9ebd512ac01aa7b00) and [New York: The Nation’s Metropolis](https://github.com/GITenberg/New-York-The-Nation-s-Metropolis_64572/tree/bdd1d8aa56d788eb439a8720b23eec20c884afb4).
