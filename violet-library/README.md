# Violet Library

Violet Library is an independent student project for discovering open-access books. The Pages deployment serves it under [/Capstone/libraries/](https://akshitashah04.github.io/Capstone/libraries/). This copy is based on the collaborative [Libraries project](https://github.com/VeedantBrahmbhatt/Libraries) with the multilingual catalog, semantic search, and student interface changes.

From the repository root, run `npm ci --prefix violet-library/frontend` and `npm run dev --prefix violet-library/frontend`. Open the URL that Vite prints. First-use model downloads are served by Hugging Face.

The feedback service is deployed independently at https://violet-library-capstone-feedback.sound-park-7168.chatgpt.site. Its private D1 database stores submitted ratings, and the Worker allows requests from the Capstone Pages origin. The Pages workflow configures the service URL. The feedback maintenance workflow calls the health endpoint daily to enforce the 90-day retention period.

## Upstream source

Capstone's [libraries-updated branch](https://github.com/akshitashah04/Capstone/tree/libraries-updated) preserves the source and commit history of the updated standalone project. Branches prefixed with [libraries-upstream/](https://github.com/akshitashah04/Capstone/branches/all?query=libraries-upstream) preserve the original upstream commits. The `violet-library/` directory on Capstone's main branch contains the adapted source, tests, documentation, evaluation assets, and upstream workflow definitions.

The Capstone Pages workflow compiles the demo into its deployment artifact and checks that the public route and catalog respond after deployment.

## Relevance score

Semantic search computes cosine similarity between the question and each book's metadata embedding. It displays the resulting score multiplied by 100, with values below 0 or above 100 capped at those bounds. Semantic + key terms adds a keyword bonus of up to 2.5 points before display. The keyword-only fallback displays its weighted term score relative to the highest result from that search. All modes rank before display rounding. Compare scores within the same search and model.

For a specific U.S. student-visa request, the search expands paraphrases and checks whether catalog metadata actually covers the requested visa or academic-student context. The same check applies in the keyword preview. If the catalog lacks a directly relevant book, the interface reports that coverage gap and offers an official external source. Ordinary topics continue to be ranked by the selected language model.
