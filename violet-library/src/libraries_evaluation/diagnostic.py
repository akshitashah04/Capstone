"""Score clearly labeled AI judgments and answer-derived target recovery."""

import argparse
import csv
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from libraries_evaluation.config import MODES
from libraries_evaluation.queries import EvaluationQuery, load_queries
from libraries_evaluation.schema import REVIEW_FIELDS
from libraries_evaluation.score import _validate_run, score_results
from libraries_search.source import sha256_file

AI_LABEL_FIELDS = ("query_id", "book_id", "grade")


def _load_run(queries_path: Path, run_dir: Path):
    queries = load_queries(queries_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("queries_sha256") != sha256_file(queries_path):
        raise ValueError("Run does not match diagnostic questions")
    ranked, timings, review = _validate_run(queries, run_dir, manifest)
    return queries, manifest, ranked, timings, review


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"Unexpected columns in {path}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"Malformed CSV row in {path}")
    return rows


def write_ai_judgments(
    queries_path: Path, run_dir: Path, labels_path: Path, output_path: Path
) -> None:
    """Overlay complete AI grades on an exact saved run, separate from human sheets."""
    queries_path, run_dir, labels_path, output_path = map(
        Path, (queries_path, run_dir, labels_path, output_path)
    )
    _queries, _manifest, _ranked, _timings, review = _load_run(queries_path, run_dir)
    labels: dict[tuple[str, str], str] = {}
    for row in _read_csv(labels_path, AI_LABEL_FIELDS):
        key = (row["query_id"], row["book_id"])
        if key not in review or key in labels:
            raise ValueError("AI labels contain an unknown or duplicate question–book pair")
        if row["grade"] not in {"0", "1", "2"}:
            raise ValueError(f"Invalid AI grade for {key[0]}/{key[1]}")
        labels[key] = row["grade"]
    if set(labels) != set(review):
        raise ValueError(f"AI labels missing {len(set(review) - set(labels))} pooled pairs")
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for key, row in review.items():
            writer.writerow({**row, "relevance": labels[key]})


def _target_metrics(
    queries: list[EvaluationQuery],
    targets: dict[str, str],
    ranked: dict[tuple[str, str], list[str]],
    timings: dict[tuple[str, str], float],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for mode in MODES:
        ranks = []
        for query in queries:
            books = ranked[(query.query_id, mode)]
            target = targets[query.query_id]
            ranks.append(books.index(target) + 1 if target in books else None)
        latencies = sorted(timings[(query.query_id, mode)] for query in queries)
        p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
        result[mode] = {
            "hit_at_1": round(sum(rank == 1 for rank in ranks) / len(ranks), 4),
            "hit_at_5": round(
                sum(rank is not None and rank <= 5 for rank in ranks) / len(ranks), 4
            ),
            "hit_at_10": round(sum(rank is not None for rank in ranks) / len(ranks), 4),
            "mrr_at_10": round(sum(1 / rank for rank in ranks if rank) / len(ranks), 4),
            "latency_p95_ms": round(p95, 3),
        }
    return result


def score_target_recovery(
    queries_path: Path, run_dir: Path, targets_path: Path
) -> dict[str, Any]:
    """Measure where each answer-derived query finds its known source book."""
    queries_path, run_dir, targets_path = map(Path, (queries_path, run_dir, targets_path))
    queries, manifest, ranked, timings, _review = _load_run(queries_path, run_dir)
    document = json.loads(targets_path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or not isinstance(document.get("targets"), list):
        raise ValueError("Unsupported target file schema")
    targets: dict[str, str] = {}
    for row in document["targets"]:
        query_id, book_id = row.get("query_id"), row.get("target_book_id")
        if not isinstance(query_id, str) or not isinstance(book_id, str) or not book_id:
            raise ValueError("Target file has an invalid question or book ID")
        if query_id in targets:
            raise ValueError("Target file has duplicate question IDs")
        targets[query_id] = book_id
    if set(targets) != {query.query_id for query in queries}:
        raise ValueError("Target file does not cover every diagnostic question exactly")
    by_language = {
        language: _target_metrics(
            [query for query in queries if query.language == language], targets, ranked, timings
        )
        for language in sorted({query.language for query in queries})
    }
    per_query = [
        {
            "query_id": query.query_id,
            "language": query.language,
            "target_book_id": targets[query.query_id],
            "rank_by_mode": {
                mode: (
                    ranked[(query.query_id, mode)].index(targets[query.query_id]) + 1
                    if targets[query.query_id] in ranked[(query.query_id, mode)]
                    else None
                )
                for mode in MODES
            },
        }
        for query in queries
    ]
    return {
        "index_revision": manifest["index_revision"],
        "queries_sha256": manifest["queries_sha256"],
        "query_count": len(queries),
        "metric_scope": "known_source_book_in_top_10",
        "overall": _target_metrics(queries, targets, ranked, timings),
        "by_language": by_language,
        "per_query": per_query,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score separate AI and answer-derived diagnostics")
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="Score complete AI labels on a saved pilot run")
    pilot.add_argument("--queries", type=Path, required=True)
    pilot.add_argument("--run-dir", type=Path, required=True)
    pilot.add_argument("--labels", type=Path, required=True)
    pilot.add_argument("--output", type=Path, required=True)
    target = commands.add_parser("targets", help="Score source-book recovery")
    target.add_argument("--queries", type=Path, required=True)
    target.add_argument("--run-dir", type=Path, required=True)
    target.add_argument("--targets", type=Path, required=True)
    target.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "pilot":
        with TemporaryDirectory() as temporary:
            judgments = Path(temporary) / "ai-judgments.csv"
            write_ai_judgments(args.queries, args.run_dir, args.labels, judgments)
            report = score_results(args.queries, args.run_dir, judgments)
        report["judgment_source"] = "AI_metadata_review_not_human"
        report["ai_labels_sha256"] = sha256_file(args.labels)
    else:
        report = score_target_recovery(args.queries, args.run_dir, args.targets)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(
        json.dumps({"query_count": report["query_count"], "metric_scope": report["metric_scope"]})
    )


if __name__ == "__main__":
    main()
