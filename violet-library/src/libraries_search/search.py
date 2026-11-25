"""Project-owned keyword, semantic, and hybrid candidate selection and ranking."""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from libraries_search.build import TextEncoder
from libraries_search.lexical import keyword_candidates
from libraries_search.model import load_model, load_reranker
from libraries_search.publish import validate_index_bundle

RRF_OFFSET = 60
MAX_CANDIDATES = 500
RERANK_POOL = 50


class PairScorer(Protocol):
    """The model interface used by the optional second-stage ranking pass."""

    def predict(self, pairs: list[tuple[str, str]], **kwargs: Any) -> np.ndarray: ...


def _rerank_text(row: sqlite3.Row) -> str:
    """Use only source-grounded title, topics, and description for pair scoring."""
    subjects = "; ".join(json.loads(row["subjects"]))
    parts = [f"Title: {row['title']}"]
    if "alternate_titles" in row.keys():
        alternate = "; ".join(json.loads(row["alternate_titles"]))
        if alternate:
            parts.append(f"Alternative title: {alternate}")
    if subjects:
        parts.append(f"Subjects: {subjects}")
    if row["abstract"]:
        parts.append(f"Description: {row['abstract'][:1_500]}")
    return "\n".join(parts)


class SearchEngine:
    """Load one checked index and rank all candidates with our own code."""

    def __init__(
        self, input_dir: Path, encoder: TextEncoder, *, reranker: PairScorer | None = None
    ):
        input_dir = Path(input_dir)
        self.manifest = validate_index_bundle(input_dir, expected_version=None)
        self.encoder = encoder
        self.reranker = reranker
        self.vectors = np.load(input_dir / "vectors.npy", mmap_mode="r", allow_pickle=False)
        self.database = sqlite3.connect(
            f"{(input_dir / 'books.sqlite').as_uri()}?mode=ro&immutable=1", uri=True
        )
        self.database.row_factory = sqlite3.Row

    def close(self) -> None:
        """Release the database handle when a CLI or service finishes."""
        self.database.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _semantic_candidates(self, query: str, limit: int) -> tuple[list[int], dict[int, float]]:
        query_vector = np.asarray(
            self.encoder.encode(
                [f"query: {query}"],
                batch_size=1,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )
        dimensions = self.manifest["dimensions"]
        if query_vector.shape != (1, dimensions) or not np.isfinite(query_vector).all():
            raise ValueError("The query model returned an invalid vector")
        if not np.allclose(np.linalg.norm(query_vector[0]), 1.0, atol=0.02):
            raise ValueError("The query model returned a vector that is not normalized")
        scores = np.asarray(self.vectors @ query_vector[0])
        count = min(limit, len(scores))
        indices = (
            np.arange(len(scores))
            if count == len(scores)
            else np.argpartition(scores, -count)[-count:]
        )
        ranked_indices = indices[np.lexsort((indices, -scores[indices]))]
        ordinals = [int(index) + 1 for index in ranked_indices]
        return ordinals, {int(index) + 1: float(scores[index]) for index in ranked_indices}

    def search(
        self, query: str, *, mode: str = "hybrid", limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return ranked book metadata and relative scores for one free-text query."""
        query = query.strip()
        if not query:
            raise ValueError("Search query is empty")
        if mode not in {"keyword", "semantic", "hybrid", "reranked"}:
            raise ValueError("Search mode must be keyword, semantic, hybrid, or reranked")
        if mode == "reranked" and self.reranker is None:
            raise ValueError("Reranked search requires a reranker model")
        if limit < 1 or limit > 100:
            raise ValueError("Search limit must be between 1 and 100")
        if offset < 0 or offset > 400:
            raise ValueError("Search offset must be between 0 and 400")
        if mode == "reranked" and offset + limit > RERANK_POOL:
            raise ValueError("Reranked pages must fit inside the 50-book candidate pool")

        candidates = min(MAX_CANDIDATES, max(100, limit + offset))
        keyword_order = (
            keyword_candidates(
                self.database, query, candidates, index_version=self.manifest["index_version"]
            )
            if mode in {"keyword", "hybrid", "reranked"}
            else []
        )
        semantic_order, similarities = (
            self._semantic_candidates(query, candidates)
            if mode in {"semantic", "hybrid", "reranked"}
            else ([], {})
        )
        keyword_ranks = {ordinal: rank for rank, ordinal in enumerate(keyword_order, start=1)}
        semantic_ranks = {ordinal: rank for rank, ordinal in enumerate(semantic_order, start=1)}
        rank_scores: dict[int, float] = {}
        for order in (keyword_order, semantic_order):
            for rank, ordinal in enumerate(order, start=1):
                rank_scores[ordinal] = rank_scores.get(ordinal, 0.0) + 1 / (RRF_OFFSET + rank)
        ordered = sorted(rank_scores, key=lambda ordinal: (-rank_scores[ordinal], ordinal))
        pool = ordered[:RERANK_POOL] if mode == "reranked" else ordered[offset : offset + limit]
        if not pool:
            return []
        placeholders = ",".join("?" for _ in pool)
        rows = self.database.execute(
            f"SELECT * FROM books WHERE ordinal IN ({placeholders})", pool
        ).fetchall()
        by_ordinal = {int(row["ordinal"]): row for row in rows}
        rerank_scores: dict[int, float] = {}
        if mode == "reranked":
            assert self.reranker is not None
            raw_scores = np.asarray(self.reranker.predict(
                [(query, _rerank_text(by_ordinal[ordinal])) for ordinal in pool],
                batch_size=16,
                show_progress_bar=False,
            ), dtype=np.float32).reshape(-1)
            if len(raw_scores) != len(pool) or not np.isfinite(raw_scores).all():
                raise ValueError("Reranker returned invalid candidate scores")
            rerank_scores = dict(zip(pool, map(float, raw_scores), strict=True))
            pool = sorted(pool, key=lambda ordinal: (
                -rerank_scores[ordinal], -rank_scores[ordinal], ordinal
            ))
            selected = pool[offset : offset + limit]
        else:
            selected = pool
        results: list[dict[str, Any]] = []
        for ordinal in selected:
            row = by_ordinal[ordinal]
            description = (row["abstract"] or "").strip()
            excerpt = description[:500].rsplit(" ", 1)[0] if len(description) > 500 else description
            results.append(
                {
                    "book_id": row["book_id"],
                    "title": row["title"],
                    "authors": json.loads(row["authors"]),
                    "subjects": json.loads(row["subjects"]),
                    "languages": json.loads(row["languages"]),
                    "publication_year": row["publication_year"],
                    "book_url": row["book_url"],
                    "description_excerpt": excerpt,
                    "description_source": (
                        row["description_source"] if "description_source" in row.keys()
                        else "abstract" if description else ""
                    ),
                    "rank_score": round(
                        rerank_scores[ordinal] if mode == "reranked" else rank_scores[ordinal],
                        8,
                    ),
                    "score_kind": (
                        "cross_encoder_relative" if mode == "reranked" else "relative_rank_fusion"
                    ),
                    "initial_rank_score": round(rank_scores[ordinal], 8),
                    "keyword_rank": keyword_ranks.get(ordinal),
                    "semantic_rank": semantic_ranks.get(ordinal),
                    "semantic_similarity": (
                        round(similarities[ordinal], 6) if ordinal in similarities else None
                    ),
                }
            )
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Search our own DOAB indexes")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--mode", choices=["keyword", "semantic", "hybrid", "reranked"], default="hybrid"
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    manifest = validate_index_bundle(args.input_dir, expected_version=None)
    model = load_model(manifest["model_repo"], manifest["model_revision"])
    reranker = load_reranker() if args.mode == "reranked" else None
    with SearchEngine(args.input_dir, model, reranker=reranker) as engine:
        print(
            json.dumps(
                engine.search(args.query, mode=args.mode, limit=args.limit, offset=args.offset),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
