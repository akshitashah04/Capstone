# NYU-inspired search demo design

## Goal and boundaries

Build a no-cost, shareable GitHub Pages prototype where visitors can type a natural-language book request, choose among the three evaluated multilingual encoders, and see five linked recommendations with up to ten on request. The UI is an independent student project and must say so prominently. It uses public DOAB metadata, no login, student profiles, server search, or external candidate-selection API.

GitHub Pages serves static files only. Hugging Face's current documentation says creating a new compute Space requires a paid plan even though CPU Basic has a zero hourly rate. Therefore the no-cost interactive version runs inference and ranking in the visitor's browser on a **bounded sample** drawn from saved full-catalog search results. This means live arbitrary queries work over the sample, not all 91,667 books. The displayed trial KPI values apply only to the earlier full-catalog evaluation, not this sample.

## Data and model behavior

Select the distinct books returned in the first ten places for the 50 authored questions across the saved E5 small v2, E5 base, and GTE trials (currently 1,884 distinct IDs). Preserve their source order and metadata. On a temporary GitHub runner, extract their already-built, verified vectors for all three models from the pinned full indexes. Commit only sample metadata and compact half-precision vectors to the Pages folder; keep the full Parquet, SQLite database, and vectors off laptops and out of Git.

The page loads one model at a time using a browser ONNX conversion and embeds the free-text query locally. E5 uses its `query:` prefix and mean pooling; GTE uses no prefix and CLS pooling, matching the trial setup. The page computes semantic cosine scores against every sampled book, keyword scores from sampled metadata, and our own reciprocal-rank fusion. The default “Best evaluated” choice maps to GTE hybrid because it had the highest assistant-reviewed full-catalog Success@5 (19/50), but this is provisional; the user can explicitly choose E5 small, E5 base, or GTE. No provider chooses candidates.

Each book card shows a source-grounded metadata excerpt, author/year/language, a source link, and a **relative relevance score** derived from the ranking formula. It must say the score only orders this query's sample results and is not a calibrated probability. A voice control may fill the text box where the browser supports speech recognition; typing remains the primary path. The model download progress, unsupported-browser state, offline state, and empty results must be explicit. The browser may cache model files; it never receives the full catalog.

## Visual direction

Use NYU Violet `#57068c`, deep violet `#330662`, ink, warm white, and cool gray. Use a simple text wordmark rather than the official NYU logo. The page is search-first: compact header, generous white space, one clear request field, understated model control, and clean result cards. Body text uses a system sans font; a restrained serif display heading adds an editorial feel without claiming access to NYU's licensed font. Meet WCAG 2.1 AA contrast, keyboard navigation, visible focus, responsive layout, and reduced-motion preferences.

## Deployment and handover

Keep source and the compact sample in `frontend/`, build output in ignored `frontend/dist/`, and setup/limitations in `Documentation/UI/`. Publish the purpose branch through the GitHub Pages Actions workflow, then verify the public URL from a clean browser. Update the root README and handover with exact start, build, deploy, and meeting-demo steps. A future production version needs a funded or approved server if it must search all 91,667 books without browser-scale downloads.

## Sources checked 2026-11-17

- [NYU Tandon design elements](https://engineering.nyu.edu/marketing-and-communications/identity-guide/design-elements) for NYU Violet and neutral colors.
- [NYU Libraries visual-branding guidance](https://guides.nyu.edu/nyu-libguide-accessibility/consistent-visual-branding) for dark purple, black/gray, and accessibility.
- [NYU Libraries homepage](https://library.nyu.edu/) for a search-first library navigation pattern.
- [GitHub Pages custom workflow guidance](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) for Actions deployment.
- [Hugging Face Spaces overview](https://huggingface.co/docs/hub/spaces-overview) for current compute-Space plan requirements.
