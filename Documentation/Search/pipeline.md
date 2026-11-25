# From a book record to a search result

```mermaid
flowchart TD
    D["DOAB metadata export"] --> P["Clean and deduplicate records"]
    P --> T["Title, author, subjects and abstract"]
    T --> V["Pinned model tokenizes and encodes each record"]
    V --> B["Normalize vectors and export the aligned browser sample"]
    P --> L["Browser keyword index"]
    S["Chinese and Hindi titles from Gutenberg and Wikisource"] --> L
    S --> E["Browser model encodes supplemental metadata"]
    B --> C["Cosine similarity over the combined catalog"]
    E --> C
    Q["Visitor's question"] --> QE["Selected browser model tokenizes and encodes query"]
    QE --> C
    Q --> K["Keyword match using the query's own script"]
    L --> K
    C --> H["Semantic mode uses cosine order; hybrid fuses both ranks"]
    K --> H
    H --> R["Show five books, with five more on request"]
    R --> F["Optional rating or none-fit report"]
    F --> G["Private review and frozen ranking evaluation"]
```

The 91,667-book research baseline encodes published metadata and abstracts. The default multilingual E5 small model uses a 512-token maximum, mean pooling and unit-length vectors. The browser uses the selected quantized model for the query and supplemental records. The E5 variants use separate query and passage prefixes. GTE base uses its first-token embedding. Cosine similarity is the dot product of the normalized vectors. In hybrid mode, reciprocal rank fusion combines semantic and keyword positions. The interface scales the best result to a relative score of 100.

The [book-text pilot](../Evaluation/book-text-pilot.md) compares metadata with partial and complete book text outside the deployed index. The [feedback review instructions](../Feedback/runbook.md#test-ranking-changes-with-reviewed-feedback) explain how to use visitor reports in an offline evaluation.
