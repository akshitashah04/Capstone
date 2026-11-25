"""Diagnose failures from a frozen, compact search run without an index download."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from libraries_evaluation.config import MODES
from libraries_evaluation.persona_score import _load_labels
from libraries_evaluation.queries import load_queries
from libraries_search.source import sha256_file


def classify_miss(
    hybrid_grades: list[int], pooled_grades: list[int], pooled_topics: list[int]
) -> str:
    """Separate an observed ranking loss from missing or uncertain evidence."""
    if 2 in hybrid_grades:
        return "success"
    if 2 in pooled_grades:
        return "ranking_loss"
    if 2 in pooled_topics:
        return "reading_need_not_verified"
    return "no_topic_fit_in_judged_pool"


def _read_csv(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8"))))


def audit_misses(run_zip: Path, labels_path: Path, queries_path: Path) -> dict[str, Any]:
    """Check saved inputs and count what the current top-five judgments can prove."""
    queries = load_queries(queries_path)
    query_ids = {query.query_id for query in queries}
    with ZipFile(run_zip) as archive:
        required = {"manifest.json", "runs.csv", "review.csv"}
        if not required.issubset(archive.namelist()):
            raise ValueError("Saved run is missing required files")
        manifest = json.loads(archive.read("manifest.json"))
        runs_bytes = archive.read("runs.csv")
        review_bytes = archive.read("review.csv")
    if manifest.get("queries_sha256") != sha256_file(queries_path):
        raise ValueError("Saved run does not match the frozen questions")
    for name, content in (("runs", runs_bytes), ("review", review_bytes)):
        if manifest.get(f"{name}_sha256") != hashlib.sha256(content).hexdigest():
            raise ValueError(f"Saved {name} checksum mismatch")
    if manifest.get("query_count") != len(queries) or manifest.get("modes") != list(MODES):
        raise ValueError("Saved run has unexpected query count or modes")

    ranked: dict[tuple[str, str], dict[int, str]] = defaultdict(dict)
    for row in _read_csv(runs_bytes):
        query_id, mode = row["query_id"], row["mode"]
        if query_id not in query_ids or mode not in MODES:
            raise ValueError("Saved run contains an unknown query or mode")
        rank = int(row["rank"])
        if rank < 1 or rank > manifest["top_k"] or rank in ranked[(query_id, mode)]:
            raise ValueError("Saved run contains a duplicate or invalid rank")
        ranked[(query_id, mode)][rank] = row["book_id"]
    expected: set[tuple[str, str]] = set()
    for query in queries:
        for mode in MODES:
            books = ranked[(query.query_id, mode)]
            if set(books) != set(range(1, len(books) + 1)) or len(books) < 5:
                raise ValueError("Saved run has a missing top-five rank")
            if len(set(books.values())) != len(books):
                raise ValueError("Saved run contains a duplicate book")
            expected.update((query.query_id, books[rank]) for rank in range(1, 6))
    labels = _load_labels(labels_path, expected)

    reviews = _read_csv(review_bytes)
    review_keys = [(row["query_id"], row["book_id"]) for row in reviews]
    if len(review_keys) != len(set(review_keys)) or not expected.issubset(review_keys):
        raise ValueError("Saved review pool is incomplete or duplicated")

    categories: Counter[str] = Counter()
    per_query = []
    for query in queries:
        query_labels = [label for (query_id, _), label in labels.items()
                        if query_id == query.query_id]
        hybrid_grades = [labels[(query.query_id, ranked[(query.query_id, "hybrid")][rank])]
                         ["overall_grade"] for rank in range(1, 6)]
        category = classify_miss(
            hybrid_grades,
            [label["overall_grade"] for label in query_labels],
            [label["topic_grade"] for label in query_labels],
        )
        categories[category] += 1
        per_query.append({
            "query_id": query.query_id,
            "category": category,
            "known_suitable_in_judged_pool": sum(
                label["overall_grade"] == 2 for label in query_labels
            ),
            "strong_topic_in_judged_pool": sum(
                label["topic_grade"] == 2 for label in query_labels
            ),
        })

    ordered_categories = {
        name: categories[name] for name in (
            "success", "ranking_loss", "reading_need_not_verified",
            "no_topic_fit_in_judged_pool"
        )
    }
    return {
        "index_revision": manifest["index_revision"],
        "queries_sha256": manifest["queries_sha256"],
        "labels_sha256": sha256_file(labels_path),
        "query_count": len(queries),
        "judged_top_five_pairs": len(labels),
        "review_pairs": len(reviews),
        "review_pairs_without_abstract": sum(not row["abstract_excerpt"].strip()
                                             for row in reviews),
        "categories": ordered_categories,
        "judged_pool_ceiling": ordered_categories["success"] + ordered_categories["ranking_loss"],
        "rankable_query_ids": [row["query_id"] for row in per_query
                               if row["category"] == "ranking_loss"],
        "per_query": per_query,
        "limits": (
            "Only the union of each baseline's top five has suitability labels. "
            "No fit in this pool does not prove the catalog has no suitable book."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit misses in a frozen persona search run")
    parser.add_argument("--run-zip", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_misses(args.run_zip, args.labels, args.queries)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"query_count": report["query_count"],
                      "categories": report["categories"]}))


if __name__ == "__main__":
    main()
