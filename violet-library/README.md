# Violet Library

Violet Library is an independent student project for discovering open-access books. The Pages deployment serves it under [/Capstone/libraries/](https://akshitashah04.github.io/Capstone/libraries/). This copy is based on the collaborative [Libraries project](https://github.com/VeedantBrahmbhatt/Libraries) with the multilingual catalog, semantic search, and student interface changes.

From the repository root, run `npm ci --prefix violet-library/frontend` and `npm run dev --prefix violet-library/frontend`. Open the URL that Vite prints. First-use model downloads are served by Hugging Face.

The feedback service is deployed independently at https://violet-library-capstone-feedback.sound-park-7168.chatgpt.site. Its private D1 database stores submitted ratings, and the Worker allows requests from the Capstone Pages origin. The Pages workflow configures the service URL. The feedback maintenance workflow calls the health endpoint daily to enforce the 90-day retention period.
