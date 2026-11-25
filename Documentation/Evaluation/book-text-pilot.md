# Book-text indexing pilot

The pilot compares metadata only, metadata plus the first 10% of the text, and metadata plus the complete text for **論語** and **道德經**. The other five supplemental records are fixed metadata-only candidates. There are six authored Chinese queries, four about specific lines and two about themes. The Analects transcription comes from Chinese Poetry and uses simplified characters. The Tao Te Ching transcription comes from the Project Gutenberg edition and uses traditional characters. The [saved result](../../evaluation/book-text/pilot-tfidf.json) records the pinned sources, text checksums, character counts, ranks, and similarity values.

The measured run uses cosine similarity on normalized TF–IDF vectors with Han bigrams. It learns term weights once and uses the best scoring metadata entry or overlapping text chunk per book. A zero sparse score means no match and is recorded without a rank.

| Indexed material | Target returned first with a positive score |
| --- | ---: |
| Metadata | 2 of 6 |
| Metadata plus 10% | 4 of 6 |
| Metadata plus full text | 6 of 6 |

The full-text arm found later passages absent from the excerpt. Quotation queries and seven candidates favor exact text lookup. This pilot does not measure semantic retrieval quality or generalize to the full catalog. More chunks also give a book more opportunities to produce a high score.

From the repository root, with Node 22+, curl, and frontend dependencies installed:

```sh
node frontend/scripts/book-text-pilot.mjs
node frontend/scripts/book-text-pilot.mjs --e5
```

The second command runs the same comparison with the pinned E5 small model used by the browser. It requires access to download its ONNX weights from Hugging Face once. The TF–IDF run completed in development. The E5 attempt was blocked by network access to Hugging Face, so there are no neural pilot results yet. The production search indexes are still metadata-based.
