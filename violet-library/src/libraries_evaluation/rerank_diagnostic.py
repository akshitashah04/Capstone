"""Compare a second-stage ranker with frozen baselines on temporary cloud storage."""

import argparse
import csv
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from huggingface_hub import snapshot_download

from libraries_evaluation.config import INDEX_DATASET_REPO
from libraries_evaluation.queries import load_queries
from libraries_search.config import RERANKER_REPO, RERANKER_REVISION
from libraries_search.model import load_model, load_reranker
from libraries_search.publish import validate_index_bundle
from libraries_search.query_needs import parse_query_needs
from libraries_search.search import RERANK_POOL, SearchEngine
from libraries_search.source import sha256_file

INDEX_REVISION = "b745902168aca10589fd0b376b58eb8019291b37"
INDEX_PATH = "search/v2"
MODES = ("keyword", "semantic", "hybrid", "reranked")
RUN_FIELDS = (
    "query_id", "mode", "rank", "book_id", "title", "authors", "subjects",
    "book_languages", "publication_year", "book_url", "description_excerpt",
    "description_source", "rank_score", "score_kind", "latency_ms",
)


class Searcher(Protocol):
    manifest: dict[str, Any]

    def search(self, query: str, *, mode: str, limit: int) -> list[dict[str, Any]]: ...


def collect_rerank_diagnostic(
    engine: Searcher, queries_path: Path, output_dir: Path, *, index_revision: str
) -> dict[str, Any]:
    """Save comparable top-ten results without assigning relevance grades."""
    if not index_revision.strip() or engine.manifest["index_version"] != 2:
        raise ValueError("A pinned v2 index revision is required")
    queries = load_queries(queries_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    runs: list[dict[str, Any]] = []
    needs = []
    for query in queries:
        needs.append({"query_id": query.query_id, "needs": asdict(parse_query_needs(query.text))})
        for mode in MODES:
            started = perf_counter()
            books = engine.search(query.text, mode=mode, limit=10)
            elapsed = round((perf_counter() - started) * 1_000, 3)
            if len({book["book_id"] for book in books}) != len(books):
                raise ValueError(f"Duplicate book in {query.query_id}/{mode}")
            for rank, book in enumerate(books, 1):
                runs.append({
                    "query_id": query.query_id,
                    "mode": mode,
                    "rank": rank,
                    "book_id": book["book_id"],
                    "title": book["title"],
                    "authors": "; ".join(book["authors"]),
                    "subjects": "; ".join(book["subjects"]),
                    "book_languages": "; ".join(book["languages"]),
                    "publication_year": book["publication_year"],
                    "book_url": book["book_url"],
                    "description_excerpt": book["description_excerpt"],
                    "description_source": book["description_source"],
                    "rank_score": book["rank_score"],
                    "score_kind": book["score_kind"],
                    "latency_ms": elapsed,
                })
    with (output_dir / "runs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RUN_FIELDS)
        writer.writeheader()
        writer.writerows(runs)
    (output_dir / "query-needs.json").write_text(
        json.dumps(needs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "index_dataset_repo": INDEX_DATASET_REPO,
        "index_revision": index_revision,
        "index_path": INDEX_PATH,
        "index_vectors_sha256": engine.manifest["vectors_npy_sha256"],
        "query_count": len(queries),
        "queries_sha256": sha256_file(queries_path),
        "modes": list(MODES),
        "reranked_candidate_pool": RERANK_POOL,
        "reranker_repo": RERANKER_REPO,
        "reranker_revision": RERANKER_REVISION,
        "judgment_status": "unjudged",
        "runs_sha256": sha256_file(output_dir / "runs.csv"),
        "query_needs_sha256": sha256_file(output_dir / "query-needs.json"),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare reranked and baseline book searches")
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Real-index diagnostics run only in GitHub Actions")
    root = Path(snapshot_download(
        repo_id=INDEX_DATASET_REPO,
        repo_type="dataset",
        revision=INDEX_REVISION,
        allow_patterns=[f"{INDEX_PATH}/*"],
        local_dir=args.index_dir,
    ))
    index_dir = root / INDEX_PATH
    index_manifest = validate_index_bundle(index_dir)
    encoder = load_model(index_manifest["model_repo"], index_manifest["model_revision"])
    reranker = load_reranker()
    with SearchEngine(index_dir, encoder, reranker=reranker) as engine:
        report = collect_rerank_diagnostic(
            engine, args.queries, args.output_dir, index_revision=INDEX_REVISION
        )
    print(json.dumps({"query_count": report["query_count"],
                      "index_revision": report["index_revision"]}), flush=True)


if __name__ == "__main__":
    main()
