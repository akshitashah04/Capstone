# Violet Library

Violet Library is an independent student project for discovering open-access books. The Pages deployment serves it under [/Capstone/libraries/](https://akshitashah04.github.io/Capstone/libraries/). This copy is based on the collaborative [Libraries project](https://github.com/VeedantBrahmbhatt/Libraries) with the multilingual catalog, semantic search, and student interface changes.

From the repository root, run `npm ci --prefix violet-library/frontend` and `npm run dev --prefix violet-library/frontend`. Open the URL that Vite prints. First-use model downloads are served by Hugging Face.

The feedback service in `feedback-api/` requires a dedicated deployment and private D1 database. Apply the SQL migrations in order, bind the database as `DB`, and configure a private `RATE_PEPPER` secret. The Worker allows the `https://akshitashah04.github.io` origin. Set the repository Actions variable `VIOLET_LIBRARY_FEEDBACK_API_URL` to the deployed HTTPS endpoint before rebuilding Pages to enable submissions.
