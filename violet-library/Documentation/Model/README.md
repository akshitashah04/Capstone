# Multilingual search model

The first search baseline uses [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), pinned in `src/libraries_search/config.py` at revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. Its model card lists an MIT license and 384-dimensional embeddings. We run the downloaded weights in our own GitHub Actions job and later in our own demo service; Hugging Face does not choose candidates. This is use of an already trained model, not training a new one.

Each book is encoded from `semantic_text` with the required `passage: ` prefix. The query uses `query: `. Vectors are normalized and compared by our code. E5 truncates text after 512 tokens, so long abstracts may lose detail; the source field order preserves titles and subjects first. Low-resource languages may perform worse. The separate keyword index covers exact words, author names, and titles.

The prepared catalog has no query-to-book relevance labels. This phase does not fine-tune E5 or claim that its cosine similarity is a probability. A graph autoencoder was discussed and excluded from the approved baseline.

The [published search manifest](https://huggingface.co/datasets/Tox1/LibrariesBookData/raw/f54ded49b97a92ca8e5dce0463500043ea2a19a4/search/v1/manifest.json) confirms 384-dimensional vectors for all 91,667 prepared books using the pinned model revision. The successful build and one smoke query confirm operation, not measured relevance across languages or student tasks.

## Experimental second ranking pass

The optional `reranked` mode uses the [multilingual MMARCO MiniLM cross-encoder](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1), pinned at revision `1427fd652930e4ba29e8149678df786c240d8825`. Our code first selects at most 50 candidates from its own keyword and E5 results, then scores the full query against each candidate's source-grounded title, subjects, and description. The model is pretrained; it was not trained on project questions or book judgments. Its raw score is for ordering, not a confidence probability.

The [v2 index](https://huggingface.co/datasets/Tox1/LibrariesBookData/tree/b745902168aca10589fd0b376b58eb8019291b37/search/v2) retains the exact E5 vectors from v1 while making more source descriptions and alternate titles available. The [50-question diagnostic](../Evaluation/query-fit-results.md) found the second pass too slow for the provisional UI latency target and left many new books unjudged. It remains experimental while hybrid on v2 is the comparison baseline. Human labels are needed before choosing or training a final model.
