"""Collect comparable search runs and an unlabeled human-review pool."""

import argparse
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from huggingface_hub import snapshot_download

from libraries_evaluation.config import INDEX_DATASET_REPO, INDEX_PATH, INDEX_REVISION, MODES
from libraries_evaluation.queries import load_queries
from libraries_evaluation.schema import REVIEW_FIELDS, RUN_FIELDS, TIMING_FIELDS
from libraries_search.model import load_model
from libraries_search.publish import validate_index_bundle
from libraries_search.search import SearchEngine
from libraries_search.source import sha256_file


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")[:100]


def collect_results(
    engine: SearchEngine,
    queries_path: Path,
    output_dir: Path,
    *,
    index_revision: str,
    top_k: int = 10,
) -> dict[str, Any]:
    """Write ranked runs, warm timings, and a deduplicated unlabeled pool."""
    if not index_revision.strip():
        raise ValueError("index_revision is required")
    if top_k < 1 or top_k > 100:
        raise ValueError("top_k must be between 1 and 100")
    queries_path = Path(queries_path)
    queries = load_queries(queries_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)

    # Model setup and the first query do not count toward warm search latency.
    for mode in MODES:
        engine.search(queries[0].text, mode=mode, limit=1)

    runs: list[dict[str, Any]] = []
    timings: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    summary_rows: list[tuple[str, str, str, str]] = []
    for query in queries:
        by_mode: dict[str, list[dict[str, Any]]] = {}
        for mode in MODES:
            started = perf_counter()
            results = engine.search(query.text, mode=mode, limit=top_k)
            elapsed_ms = (perf_counter() - started) * 1_000
            book_ids = [result["book_id"] for result in results]
            if len(book_ids) != len(set(book_ids)):
                raise ValueError(f"Duplicate book in {query.query_id}/{mode} results")
            by_mode[mode] = results
            timings.append(
                {
                    "query_id": query.query_id,
                    "mode": mode,
                    "latency_ms": round(elapsed_ms, 3),
                    "result_count": len(results),
                }
            )
            for rank, result in enumerate(results, 1):
                runs.append(
                    {
                        "query_id": query.query_id,
                        "mode": mode,
                        "rank": rank,
                        "book_id": result["book_id"],
                        "rank_score": result["rank_score"],
                        "semantic_similarity": result["semantic_similarity"],
                    }
                )

        pooled: dict[str, dict[str, Any]] = {}
        ranks: dict[str, dict[str, int]] = {mode: {} for mode in MODES}
        for mode in MODES:
            for rank, result in enumerate(by_mode[mode], 1):
                pooled.setdefault(result["book_id"], result)
                ranks[mode][result["book_id"]] = rank
        for book_id in sorted(
            pooled,
            key=lambda item: (min(ranks[mode].get(item, top_k + 1) for mode in MODES), item),
        ):
            result = pooled[book_id]
            row = engine.database.execute(
                "SELECT abstract FROM books WHERE book_id = ?", (book_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Book {book_id} is missing from the index database")
            reviews.append(
                {
                    "query_id": query.query_id,
                    "query_text": query.text,
                    "query_language": query.language,
                    "query_intent": query.intent,
                    "query_split": query.split,
                    "book_id": book_id,
                    "title": result["title"],
                    "authors": "; ".join(result["authors"]),
                    "subjects": "; ".join(result["subjects"]),
                    "book_languages": "; ".join(result["languages"]),
                    "publication_year": result["publication_year"],
                    "book_url": result["book_url"],
                    "abstract_excerpt": (row["abstract"] or "").strip()[:600],
                    "keyword_rank": ranks["keyword"].get(book_id, ""),
                    "semantic_rank": ranks["semantic"].get(book_id, ""),
                    "hybrid_rank": ranks["hybrid"].get(book_id, ""),
                    "relevance": "",
                }
            )
        hybrid_top = by_mode["hybrid"][0]["title"] if by_mode["hybrid"] else "No result"
        summary_rows.append((query.query_id, query.language, query.text, hybrid_top))

    _write_csv(output_dir / "runs.csv", RUN_FIELDS, runs)
    _write_csv(output_dir / "timings.csv", TIMING_FIELDS, timings)
    _write_csv(output_dir / "review.csv", REVIEW_FIELDS, reviews)
    summary = [
        "# Unjudged pilot search results",
        "",
        "These examples verify the query path only. Human relevance labels are still required.",
        "",
        "| Query ID | Language | Question | Top hybrid book |",
        "| --- | --- | --- | --- |",
    ]
    summary.extend(
        f"| {_table_cell(query_id)} | {language} | {_table_cell(text)} | "
        f"{_table_cell(title)} |"
        for query_id, language, text, title in summary_rows
    )
    summary.extend(
        [
            "",
            "## Review pool",
            "",
            "Use the book ID when recording a 0, 1, or 2 grade. Blank grades remain unjudged.",
            "",
            "| Query ID | Book ID | Title | K / S / H rank | Abstract preview | Source |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in reviews:
        rank_text = " / ".join(str(row[f"{mode}_rank"] or "–") for mode in MODES)
        source = f"[Open]({row['book_url']})" if row["book_url"].startswith("https://") else ""
        summary.append(
            f"| {_table_cell(row['query_id'])} | {_table_cell(row['book_id'])} | "
            f"{_table_cell(row['title'])} | {rank_text} | "
            f"{_table_cell(row['abstract_excerpt'])} | {source} |"
        )
    (output_dir / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "index_dataset_repo": INDEX_DATASET_REPO,
        "index_revision": index_revision,
        "index_path": INDEX_PATH,
        "index_books_indexed": engine.manifest["books_indexed"],
        "index_source_revision": engine.manifest["source_revision"],
        "index_model_revision": engine.manifest["model_revision"],
        "index_vectors_sha256": engine.manifest["vectors_npy_sha256"],
        "queries_sha256": sha256_file(queries_path),
        "runs_sha256": sha256_file(output_dir / "runs.csv"),
        "timings_sha256": sha256_file(output_dir / "timings.csv"),
        "review_sha256": sha256_file(output_dir / "review.csv"),
        "query_count": len(queries),
        "candidate_count": len(reviews),
        "top_k": top_k,
        "modes": list(MODES),
        "judgment_status": "unjudged",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect cloud-only search evaluation results")
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Real-index evaluation runs only in GitHub Actions")
    root = Path(
        snapshot_download(
            repo_id=INDEX_DATASET_REPO,
            repo_type="dataset",
            revision=INDEX_REVISION,
            allow_patterns=[f"{INDEX_PATH}/*"],
            local_dir=args.index_dir,
        )
    )
    index_dir = root / INDEX_PATH
    index_manifest = validate_index_bundle(index_dir, expected_version=None)
    encoder = load_model(index_manifest["model_repo"], index_manifest["model_revision"])
    with SearchEngine(index_dir, encoder) as engine:
        manifest = collect_results(
            engine, args.queries, args.output_dir, index_revision=INDEX_REVISION, top_k=args.top_k
        )
    print(
        json.dumps(
            {
                "query_count": manifest["query_count"],
                "candidate_count": manifest["candidate_count"],
                "judgment_status": manifest["judgment_status"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
