# Query fit and collection coverage: first five steps

This record follows the agreed order and stops before human ratings and the final acceptance retest. The goal is **more than 40 of 50 searches with a clearly suitable book in the first five**. The runs below do not establish that result. They use the same 50 fictional questions, not real student queries.

## 1. Review the misses

The repeatable [miss audit](../../evaluation/personas/miss-audit.json) validates the frozen search artifact and its separate assistant labels. Of 50 hybrid searches, 15 already had a clearly suitable book in the first five. Among the other 35:

| What the existing judgments show | Questions | Meaning |
| --- | ---: | --- |
| Suitable book was in another mode's first five | 4 | A ranking change can recover a known book. |
| Strong topic match, but reading need not verified | 12 | Better descriptions or human inspection may resolve the uncertainty. |
| No strong topic match in the judged first-five pool | 19 | Search deeper and test another collection; this does **not** prove the catalog has no suitable book. |

Only 19 of 50 questions have a clearly suitable book **anywhere in the judged pool**. This is a ceiling for rearranging those already judged books, not a ceiling for the full DOAB catalog. Of 1,113 distinct books in the saved top-ten review pool, 133 had no abstract preview. The audit is implemented in `src/libraries_evaluation/miss_audit.py` and tested without downloading the full index.

## 2. Improve available metadata

The [cloud source audit](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43780665827) scanned the pinned DOAB Parquet file on a temporary runner. Its [small report](../../evaluation/metadata/field-audit.json) found 13,125 books without a primary abstract, but **10,598** of those have a source-provided alternate-language abstract. It also found 39,969 books with an alternate title. The other 2,527 books still lack both descriptions. A classification exists for 3,817 of 5,763 books without subject keywords, but classification values were not promoted to subject labels without checking their meaning.

The [v2 cloud upgrade](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43781216697) built a new SQLite book index with alternate titles searchable and a source-provided description fallback. It retained the **same 91,667 books and exactly the same meaning vectors** as v1, checked every book ID against the pinned source order, and published the verified files at [DOAB search index v2](https://huggingface.co/datasets/Tox1/LibrariesBookData/tree/b745902168aca10589fd0b376b58eb8019291b37/search/v2). The old v1 index remains available. Results now include a bounded description excerpt and its source field; an alternate-language description is identified as such, not translated or rewritten.

## 3. Read explicit needs in the question

`src/libraries_search/query_needs.py` extracts only stated signals for introductory or advanced reading, examples, methods, practical use, and avoiding code or math. It does not use a student profile. On the frozen 50 questions it found 14 explicit introductory signals, 11 advanced signals, and left 25 levels unknown. This is deliberately cautious: a major alone is not proof of reading level. The complete original question still goes to meaning search and the second ranking pass.

## 4. Check candidate books again

An optional `reranked` mode uses our own keyword and semantic search to gather up to 50 books, then compares each book's source-grounded title, subjects, and description against the full question. It uses the [pinned multilingual MMARCO MiniLM model](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) in our code. The model is not trained on our 50 questions. Its score is a relative sorting value, **not** a confidence percentage.

The [50-question cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43781681831) is saved as a [compact result artifact](../../evaluation/query-fit/reranked-run.zip). Reusing old assistant labels gives only a **known-good lower bound**: 10 keyword, 14 semantic, 17 hybrid, and 15 reranked questions have a previously rated suitable book in the first five. There are 38, 0, 31, and **129 unjudged top-five book pairs**, respectively, so these are not comparable final success rates. On the temporary runner, reranked search took about **6.6 seconds at the median and 7.5 seconds at the 95th percentile**, excluding model startup, network, and UI. Some first results are visibly weak or in a different language from the query. This mode is **experimental and not the recommended UI default**.

## 5. Check whether another collection helps

The [Open Textbook Library](https://open.umn.edu/opentextbooks/discovery) offers a cumulative unfiltered CSV of CC0 catalog records. Its individual book licenses vary. We downloaded that full file only on a temporary cloud runner, built **our own** temporary 1,915-book search index, and checked the 19 questions with no strong topic match in the earlier judged DOAB pool. No provider search endpoint selected the candidates. The [coverage run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43782166940) and [compact result artifact](../../evaluation/query-fit/otl-coverage-run.zip) record the source checksum, all 95 first-five results, and their links.

All 1,915 valid CSV records had a description and subject, but this CSV does not supply a language field, so language is left unknown. A few books merit review, such as **Web Literacy for Student Fact-Checkers** for the journalism question and **Leveraging Data Visualization to Communicate Effectively** for the chart question. Many other results are weak or off topic. The current [JSON API](https://open.umn.edu/opentextbooks/api-docs/index.html) reports a different total than the CSV; the pilot is limited to the exact CSV snapshot identified by checksum. The supplement remains a **separate experiment**, with no silent additions to the DOAB index. Before merging it, verify book language, duplicates against all DOAB records, link health, and fit with human ratings.

## Decision and next boundary

Metadata coverage improved, and the first 50-question diagnostic exposes both ranking and collection gaps. The available evidence does **not** show more than 40 of 50 suitable first-five results. Keep hybrid on the v2 index as the current baseline, keep reranked and the textbook supplement experimental, and proceed next to **human ratings of natural questions**. The existing 233-pair human sheets belong to the frozen v1 pilot; a new v2 candidate pool must be collected before judging v2. After that, tune and retest on a held-out set, including response time. A shareable five-result UI and free deployment can then use the chosen, tested ranking path; GitHub Pages alone cannot run the Python index or models.

The **free live-backend choice is not yet settled**. [Hugging Face's current Spaces policy](https://huggingface.co/docs/hub/spaces-overview) requires a paid plan for new Gradio/Docker compute Spaces except eligible free ZeroGPU Spaces; [Render's free web service](https://render.com/docs/compute-plans) has 512 MB RAM, which is a tight fit for this index plus a model. The UI phase must test an eligible free runtime or reduce the serving footprint before promising a stable public link. Static GitHub Pages could host the page, but still needs a separate live search backend.

**Next phase started:** [separate rank-blind v2 review packets](../../evaluation/review/query-fit-v2/README.md) now hold the first-five DOAB and textbook candidates with blank human grades. This historical first-five-step report remains a diagnostic; [the review runbook](human-review-v2-runbook.md) gives the next team action.
