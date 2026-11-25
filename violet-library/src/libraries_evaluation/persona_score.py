"""Compare search modes for fictional student goals and reading needs."""

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from libraries_evaluation.config import MODES
from libraries_evaluation.personas import load_personas
from libraries_evaluation.queries import EvaluationQuery, load_queries
from libraries_evaluation.score import _validate_run, ndcg_at_k
from libraries_search.source import sha256_file

LABEL_FIELDS = ("query_id", "book_id", "topic_grade", "level_fit", "overall_grade")
LEVEL_FITS = {"yes", "no", "unclear"}


def _load_labels(
    path: Path, expected: set[tuple[str, str]]
) -> dict[tuple[str, str], dict[str, Any]]:
    labels: dict[tuple[str, str], dict[str, Any]] = {}
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != LABEL_FIELDS:
            raise ValueError("Persona labels have unexpected columns")
        for row in reader:
            key = (row["query_id"], row["book_id"])
            if key not in expected or key in labels:
                raise ValueError("Persona labels contain an unknown or duplicate top-five pair")
            if (
                None in row or any(value is None for value in row.values())
                or row["topic_grade"] not in {"0", "1", "2"}
                or row["overall_grade"] not in {"0", "1", "2"}
                or row["level_fit"] not in LEVEL_FITS
            ):
                raise ValueError(f"Invalid persona grade for {key[0]}/{key[1]}")
            topic, overall = int(row["topic_grade"]), int(row["overall_grade"])
            if overall > topic or (overall == 2 and row["level_fit"] != "yes"):
                raise ValueError(f"Inconsistent persona grade for {key[0]}/{key[1]}")
            labels[key] = {"topic_grade": topic, "overall_grade": overall,
                           "level_fit": row["level_fit"]}
    if set(labels) != expected:
        raise ValueError(f"Persona labels missing {len(expected - set(labels))} top-five pairs")
    return labels


def _group_metrics(
    queries: list[EvaluationQuery],
    ranked: dict[tuple[str, str], list[str]],
    timings: dict[tuple[str, str], float],
    labels: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {"sample_count": len(queries)}
    for mode in MODES:
        top_one, success, topic_success, ndcgs, latencies = [], [], [], [], []
        for query in queries:
            books = ranked[(query.query_id, mode)][:5]
            grades = [labels[(query.query_id, book)]["overall_grade"] for book in books]
            topics = [labels[(query.query_id, book)]["topic_grade"] for book in books]
            pool = [label["overall_grade"] for (query_id, _book), label in labels.items()
                    if query_id == query.query_id]
            top_one.append(float(bool(grades) and grades[0] == 2))
            success.append(float(2 in grades))
            topic_success.append(float(2 in topics))
            ndcgs.append(ndcg_at_k(grades, pool, 5))
            latencies.append(timings[(query.query_id, mode)])
        ordered = sorted(latencies)
        result[mode] = {
            "top_one_strong_rate": round(sum(top_one) / len(queries), 4),
            "success_at_5": round(sum(success) / len(queries), 4),
            "topical_success_at_5": round(sum(topic_success) / len(queries), 4),
            "pooled_ndcg_at_5": round(sum(ndcgs) / len(queries), 4),
            "latency_p95_ms": round(ordered[math.ceil(0.95 * len(ordered)) - 1], 3),
        }
    return result


def score_persona_results(
    personas_path: Path, queries_path: Path, run_dir: Path, labels_path: Path
) -> dict[str, Any]:
    """Score complete assistant judgments for the union of all top-five results."""
    personas = load_personas(personas_path)
    queries = load_queries(queries_path)
    if len(personas) != len(queries) or any(
        persona["persona_id"] != query.query_id
        or persona["query"] != query.text
        or persona["language"] != query.language
        for persona, query in zip(personas, queries, strict=True)
    ):
        raise ValueError("Personas and frozen search questions differ")
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("queries_sha256") != sha256_file(queries_path):
        raise ValueError("Search run does not match the frozen persona questions")
    ranked, timings, review = _validate_run(queries, run_dir, manifest)
    expected = {(query.query_id, book) for query in queries for mode in MODES
                for book in ranked[(query.query_id, mode)][:5]}
    labels = _load_labels(labels_path, expected)
    by_id = {persona["persona_id"]: persona for persona in personas}
    per_persona = []
    for query in queries:
        mode_scores = {}
        top_books = {}
        first_strong = {}
        pool = [label["overall_grade"] for (query_id, _book), label in labels.items()
                if query_id == query.query_id]
        for mode in MODES:
            books = ranked[(query.query_id, mode)][:5]
            grades = [labels[(query.query_id, book)]["overall_grade"] for book in books]
            mode_scores[mode] = round(ndcg_at_k(grades, pool, 5), 4)
            first_strong[mode] = next((rank for rank, grade in enumerate(grades, 1)
                                       if grade == 2), None)
            if books:
                book = books[0]
                top_books[mode] = {
                    "book_id": book,
                    "title": review[(query.query_id, book)]["title"],
                    **labels[(query.query_id, book)],
                }
            else:
                top_books[mode] = None
        maximum = max(mode_scores.values())
        per_persona.append({
            "persona_id": query.query_id,
            "level": by_id[query.query_id]["level"],
            "major": by_id[query.query_id]["major"],
            "language": query.language,
            "query": query.text,
            "first_strong_rank_by_mode": first_strong,
            "ndcg_at_5_by_mode": mode_scores,
            "best_modes": ([mode for mode in MODES if mode_scores[mode] == maximum]
                           if maximum > 0 else []),
            "top_book_by_mode": top_books,
        })
    return {
        "metric_scope": "assistant_judged_union_of_top_5",
        "index_revision": manifest["index_revision"],
        "queries_sha256": manifest["queries_sha256"],
        "labels_sha256": sha256_file(labels_path),
        "query_count": len(queries),
        "judged_pairs": len(labels),
        "grade_counts": dict(Counter(str(label["overall_grade"]) for label in labels.values())),
        "level_fit_counts": dict(Counter(label["level_fit"] for label in labels.values())),
        "metrics": {
            "overall": _group_metrics(queries, ranked, timings, labels),
            "by_level": {level: _group_metrics(
                [query for query in queries if by_id[query.query_id]["level"] == level],
                ranked, timings, labels,
            ) for level in ("undergraduate", "graduate") if any(
                by_id[query.query_id]["level"] == level for query in queries)},
            "by_language": {language: _group_metrics(
                [query for query in queries if query.language == language],
                ranked, timings, labels,
            ) for language in sorted({query.language for query in queries})},
        },
        "per_persona": per_persona,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score 50 synthetic student search scenarios")
    parser.add_argument("--personas", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score_persona_results(args.personas, args.queries, args.run_dir, args.labels)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"query_count": report["query_count"],
                      "judged_pairs": report["judged_pairs"]}))


if __name__ == "__main__":
    main()
