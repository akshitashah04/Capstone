# Prepared catalog data dictionary

The output is `data/books.parquet` in [the shared Hugging Face dataset](https://huggingface.co/datasets/Tox1/LibrariesBookData). One row is one DOAB **book record**. The source is DOAB's direct full repository CSV export at `https://directory.doabooks.org/download-export?format=csv`, whose header and sample records were inspected live on 2026-11-14. Empty strings and empty lists mean the source did not provide a usable value; no values are invented. The Parquet schema is versioned in `src/libraries_data/schema.py`.

| Output column | Direct DOAB export column | Preparation and reason |
| --- | --- | --- |
| `book_id` | `id` | Stable identity; deduplication and later updates. |
| `title` | `dc.title` | Original display title and strongest search signal; required. |
| `alternate_titles` | `dc.title.alternative` | Other searchable title forms, kept separately. |
| `authors` | `dc.contributor.author` | Exact author search and display. |
| `subjects` | `dc.subject.other` | Topic keywords for semantic and keyword search. |
| `classifications` | `dc.subject.classification`, `dc.subject` | Broad subjects and classification codes for browsing or filters; excluded from `semantic_text` to avoid noise. |
| `abstract` | `dc.description.abstract` | Main description for semantic comparison; books without one remain in the catalog. |
| `other_language_abstract` | `oapen.abstract.otherlanguage` | Additional description text when present. |
| `languages` | `dc.language` | Extract codes from values such as `English[eng]`; no translation. |
| `publication_year` | `dc.date.issued` | Leading four-digit year for display or filters. |
| `isbns` | `BITSTREAM ISBN`, `oapen.relation.isbn` | Exact identifier lookup; unique values kept in source order. |
| `doi` | `oapen.identifier.doi` | Exact identifier lookup; DOI URL prefix removed. |
| `publisher` | `oapen.relation.isPublishedBy_publisher.name`, then `oapen.imprint` | Display and filtering. |
| `book_url` | `dc.identifier.uri` | Canonical DOAB record link. |
| `download_url` | `BITSTREAM Download URL`, then `oapen.identifier.downloadUrl` | Direct access link when provided. |
| `license_url` | `BITSTREAM License`, then `dc.rights.licenseurl` | Shows the book's own license; separate from metadata CC0. |
| `semantic_text` | Derived from title, alternate titles, subject keywords, and descriptions | Ready input for future model experiments; source fields remain available for other weighting choices. |

Text is HTML-unescaped, stripped of simple markup, whitespace-normalized, and Unicode-normalized to NFC. Accents, scripts, and original wording are preserved. The export joins multiple values with `||`; those become separate list entries without splitting ordinary semicolons inside a value. Deduplication uses only `book_id`; books with the same title, DOI, or ISBN may be distinct editions or translations.

## Exclusions and checks

Rows whose `dc.type` is not `book` are excluded. Book rows without an ID or title are rejected and counted. Publication requires at least 90,000 unique books: the direct export yielded 91,667 books on 2026-11-14, so this gate catches a substantially smaller or interrupted snapshot. It does not prove that the export matches every title on DOAB's live site, which advertises over 111,000 books. The quality report counts duplicates and missing abstracts, subjects, languages, and record URLs. Missing fields are measured, not guessed.

The direct export includes many fields that are irrelevant to search, including administrative contact information. The prepared dataset selects only the fields above. The first smaller CSV feed and the OAI-PMH harvest trials are recorded in the session log. `semantic_text` is **not** an embedding, model score, confidence score, or relevance label. The metadata does not include NYU holdings or book full text.

Source and terms: https://doabooks.org/en/librarians/doab-metadata and https://www.doabooks.org/en/researchers/full-faq
