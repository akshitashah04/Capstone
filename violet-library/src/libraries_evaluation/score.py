"""Score complete human judgments without treating unknown books as irrelevant."""

import argparse
import csv
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libraries_evaluation.config import MODES
from libraries_evaluation.queries import EvaluationQuery, load_queries
from libraries_evaluation.schema import REVIEW_FIELDS, RUN_FIELDS, TIMING_FIELDS
from libraries_search.source import sha256_file


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"Unexpected columns in {path.name}")
        return list(reader)


def ndcg_at_k(ranked_grades: list[int], pool_grades: list[int], k: int) -> float:
    """Calculate graded nDCG using the judged candidate pool as the ideal set."""
    if k < 1:
        raise ValueError("nDCG cutoff must be positive")

    def discounted_gain(grades: list[int]) -> float:
        return sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades[:k], 1))

    ideal = discounted_gain(sorted(pool_grades, reverse=True))
    return discounted_gain(ranked_grades) / ideal if ideal else 0.0


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _validate_run(
    queries: list[EvaluationQuery], run_dir: Path, manifest: dict[str, Any]
) -> tuple[
    dict[tuple[str, str], list[str]],
    dict[tuple[str, str], float],
    dict[tuple[str, str], dict[str, str]],
]:
    if manifest.get("schema_version") != 1 or manifest.get("modes") != list(MODES):
        raise ValueError("Evaluation run schema or modes are unsupported")
    if manifest.get("query_count") != len(queries):
        raise ValueError("Evaluation run query count changed")
    top_k = manifest.get("top_k")
    if top_k != 10:
        raise ValueError("Scored nDCG@10 requires a run collected with top_k=10")
    for filename, key in (
        ("runs.csv", "runs_sha256"),
        ("timings.csv", "timings_sha256"),
        ("review.csv", "review_sha256"),
    ):
        if sha256_file(run_dir / filename) != manifest.get(key):
            raise ValueError(f"Evaluation run checksum mismatch: {filename}")

    query_ids = {query.query_id for query in queries}
    runs = _read_csv(run_dir / "runs.csv", RUN_FIELDS)
    grouped: dict[tuple[str, str], dict[int, str]] = {}
    for row in runs:
        key = (row["query_id"], row["mode"])
        if key[0] not in query_ids or key[1] not in MODES:
            raise ValueError("Evaluation run has an unknown query or mode")
        try:
            rank = int(row["rank"])
        except ValueError as error:
            raise ValueError("Evaluation run has an invalid rank") from error
        if rank < 1 or rank > top_k or not row["book_id"]:
            raise ValueError("Evaluation run has an invalid rank or book ID")
        slots = grouped.setdefault(key, {})
        if rank in slots or row["book_id"] in slots.values():
            raise ValueError("Evaluation run has duplicate ranks or books")
        slots[rank] = row["book_id"]
    ranked: dict[tuple[str, str], list[str]] = {}
    for query in queries:
        for mode in MODES:
            key = (query.query_id, mode)
            slots = grouped.get(key, {})
            if set(slots) != set(range(1, len(slots) + 1)):
                raise ValueError("Evaluation run ranks are not consecutive")
            ranked[key] = [slots[rank] for rank in sorted(slots)]

    timings: dict[tuple[str, str], float] = {}
    for row in _read_csv(run_dir / "timings.csv", TIMING_FIELDS):
        key = (row["query_id"], row["mode"])
        if key not in ranked or key in timings:
            raise ValueError("Evaluation run has missing or duplicate timing keys")
        try:
            latency = float(row["latency_ms"])
            result_count = int(row["result_count"])
        except ValueError as error:
            raise ValueError("Evaluation run has invalid timing values") from error
        if not math.isfinite(latency) or latency < 0 or result_count != len(ranked[key]):
            raise ValueError("Evaluation timing does not match its result list")
        timings[key] = latency
    if set(timings) != set(ranked):
        raise ValueError("Evaluation run is missing a query timing")

    review: dict[tuple[str, str], dict[str, str]] = {}
    for row in _read_csv(run_dir / "review.csv", REVIEW_FIELDS):
        key = (row["query_id"], row["book_id"])
        if key in review or key[0] not in query_ids or not key[1]:
            raise ValueError("Review pool has duplicate or unknown question–book pairs")
        review[key] = row
    expected_pool = {
        (query_id, book_id)
        for (query_id, _mode), book_ids in ranked.items()
        for book_id in book_ids
    }
    if set(review) != expected_pool or manifest.get("candidate_count") != len(review):
        raise ValueError("Review pool does not match the ranked results")
    return ranked, timings, review


def _validate_judgments(
    path: Path, review: dict[tuple[str, str], dict[str, str]]
) -> dict[tuple[str, str], int]:
    labels: dict[tuple[str, str], int] = {}
    missing: list[tuple[str, str]] = []
    for row in _read_csv(path, REVIEW_FIELDS):
        key = (row["query_id"], row["book_id"])
        if key not in review or key in labels:
            raise ValueError("Judgments have an unknown or duplicate question–book pair")
        for field in REVIEW_FIELDS:
            if field != "relevance" and row[field] != review[key][field]:
                raise ValueError(f"Judgment metadata changed for {key[0]}/{key[1]}")
        grade = row["relevance"].strip()
        if not grade:
            missing.append(key)
        elif grade not in {"0", "1", "2"}:
            raise ValueError(f"Invalid relevance grade for {key[0]}/{key[1]}")
        else:
            labels[key] = int(grade)
    missing.extend(set(review) - set(labels) - set(missing))
    if missing:
        raise ValueError(f"Missing judgments for {len(missing)} pooled pairs")
    return labels


def _group_metrics(
    queries: list[EvaluationQuery],
    ranked: dict[tuple[str, str], list[str]],
    timings: dict[tuple[str, str], float],
    labels: dict[tuple[str, str], int],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "sample_count": len(queries),
        "known_title_count": sum(query.intent == "known_title" for query in queries),
    }
    for mode in MODES:
        successes: list[float] = []
        ndcgs: list[float] = []
        known_titles: list[float] = []
        latencies: list[float] = []
        for query in queries:
            key = (query.query_id, mode)
            book_ids = ranked[key]
            grades = [labels[(query.query_id, book_id)] for book_id in book_ids]
            pool_grades = [
                grade
                for (query_id, _book_id), grade in labels.items()
                if query_id == query.query_id
            ]
            successes.append(float(any(grade == 2 for grade in grades[:5])))
            ndcgs.append(ndcg_at_k(grades, pool_grades, 10))
            latencies.append(timings[key])
            if query.intent == "known_title":
                known_titles.append(float(bool(book_ids) and book_ids[0] == query.expected_book_id))
        result[mode] = {
            "success_at_5": round(sum(successes) / len(queries), 4),
            "pooled_ndcg_at_10": round(sum(ndcgs) / len(queries), 4),
            "known_title_top_1": (
                round(sum(known_titles) / len(known_titles), 4) if known_titles else None
            ),
            "latency_p95_ms": round(_p95(latencies), 3),
        }
    keyword = result["keyword"]["pooled_ndcg_at_10"]
    hybrid = result["hybrid"]["pooled_ndcg_at_10"]
    result["hybrid_vs_keyword_ndcg_relative_gain"] = (
        round((hybrid - keyword) / keyword, 4) if keyword else None
    )
    return result


def _abstract_presence(
    review: dict[tuple[str, str], dict[str, str]], labels: dict[tuple[str, str], int]
) -> dict[str, dict[str, float | int | None]]:
    """Describe judged candidates by abstract availability, without causal claims."""
    groups: dict[str, list[int]] = {"with_abstract": [], "without_abstract": []}
    for key, row in review.items():
        name = "with_abstract" if row["abstract_excerpt"].strip() else "without_abstract"
        groups[name].append(labels[key])
    return {
        name: {
            "candidate_count": len(grades),
            "clearly_relevant_rate": (
                round(sum(grade == 2 for grade in grades) / len(grades), 4) if grades else None
            ),
        }
        for name, grades in groups.items()
    }


def score_results(
    queries_path: Path, run_dir: Path, judgments_path: Path
) -> dict[str, Any]:
    """Reject incomplete labels, then score comparable modes and groups."""
    queries_path = Path(queries_path)
    run_dir = Path(run_dir)
    queries = load_queries(queries_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if sha256_file(queries_path) != manifest.get("queries_sha256"):
        raise ValueError("Evaluation question checksum mismatch")
    ranked, timings, review = _validate_run(queries, run_dir, manifest)
    labels = _validate_judgments(Path(judgments_path), review)
    by_split = {
        split: _group_metrics(
            [query for query in queries if query.split == split], ranked, timings, labels
        )
        for split in sorted({query.split for query in queries})
    }
    by_language = {
        language: _group_metrics(
            [query for query in queries if query.language == language], ranked, timings, labels
        )
        for language in sorted({query.language for query in queries})
    }
    return {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "index_revision": manifest["index_revision"],
        "queries_sha256": manifest["queries_sha256"],
        "query_count": len(queries),
        "judged_pairs": len(labels),
        "metric_scope": "judged_top_10_pool",
        "abstract_presence": _abstract_presence(review, labels),
        "metrics": {
            "overall": _group_metrics(queries, ranked, timings, labels),
            "by_split": by_split,
            "by_language": by_language,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score fully judged book search runs")
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Real-data evaluation runs only in GitHub Actions")
    report = score_results(args.queries, args.run_dir, args.judgments)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps({"query_count": report["query_count"], "judged_pairs": report["judged_pairs"]})
    )


if __name__ == "__main__":
    main()
