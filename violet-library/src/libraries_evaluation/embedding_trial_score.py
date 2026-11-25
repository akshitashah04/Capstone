"""Score assistant-reviewed, checksum-validated embedding model trials."""

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from libraries_evaluation.assistant_v2_score import _load_labels
from libraries_evaluation.embedding_model_trial import (
    MODES,
    RUN_FIELDS,
    TRIAL_MODELS,
    TrialModel,
)
from libraries_evaluation.queries import load_queries
from libraries_search.source import sha256_file

TOP_K = 5
SOURCE_FIELDS = (
    "title", "authors", "subjects", "book_languages", "publication_year",
    "book_url", "description_excerpt", "description_source",
)


def score_trial(
    queries_path: Path, result_dir: Path, labels_path: Path, spec: TrialModel
) -> dict[str, Any]:
    """Require complete frozen evidence before computing first-five fit."""
    result_dir = Path(result_dir)
    manifest = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
    queries = load_queries(queries_path)
    query_map = {query.query_id: query for query in queries}
    expected_manifest = {
        "model_key": spec.key, "model_repo": spec.repo,
        "model_revision": spec.revision,
        "query_count": len(queries),
        "queries_sha256": sha256_file(queries_path),
        "modes": list(MODES), "top_k": 10,
        "judgment_status": "unjudged",
    }
    for key, value in expected_manifest.items():
        if manifest.get(key) != value:
            raise ValueError(f"Trial manifest has wrong {key}")
    if not manifest.get("index_vectors_sha256"):
        raise ValueError("Trial manifest has no vector checksum")
    runs_path = result_dir / "runs.csv"
    if sha256_file(runs_path) != manifest.get("runs_sha256"):
        raise ValueError("Trial runs checksum mismatch")
    with runs_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != RUN_FIELDS:
            raise ValueError("Trial runs have unexpected columns")
        rows = list(reader)
    if len(rows) != len(queries) * len(MODES) * 10:
        raise ValueError("Trial runs have incomplete rankings")

    ranked: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    metadata: dict[tuple[str, str], tuple[str, ...]] = {}
    timings: dict[tuple[str, str], float] = {}
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Trial runs contain a malformed row")
        qid, mode, bid = row["query_id"], row["mode"], row["book_id"]
        if qid not in query_map or mode not in MODES or not bid:
            raise ValueError("Trial runs contain an unknown question, mode, or book")
        try:
            rank = int(row["rank"])
            latency = float(row["latency_ms"])
            score = float(row["rank_score"])
        except ValueError as error:
            raise ValueError("Trial runs contain a nonnumeric ranking value") from error
        if (rank < 1 or rank > 10 or not math.isfinite(latency) or latency < 0
                or not math.isfinite(score)):
            raise ValueError("Trial runs contain an invalid rank, score, or time")
        key = (qid, mode)
        ranked[key].append((rank, bid))
        if rank == 1:
            timings[key] = latency
        source = tuple(row[field] for field in SOURCE_FIELDS)
        if not row["book_url"].startswith("https://"):
            raise ValueError("Trial book has no HTTPS source link")
        pair = (qid, bid)
        if pair in metadata and metadata[pair] != source:
            raise ValueError("Trial book metadata changed between modes")
        metadata[pair] = source
    for qid in query_map:
        for mode in MODES:
            books = ranked[(qid, mode)]
            if sorted(rank for rank, _ in books) != list(range(1, 11)):
                raise ValueError("Trial rankings have missing or duplicate ranks")
            if len({bid for _, bid in books}) != 10:
                raise ValueError("Trial rankings repeat a book")
            if (qid, mode) not in timings:
                raise ValueError("Trial rankings have no timing")

    expected_pairs = {
        (qid, bid) for (qid, _mode), books in ranked.items()
        for rank, bid in books if rank <= TOP_K
    }
    labels = _load_labels(labels_path, expected_pairs)

    def metrics_for(ids: list[str]) -> dict[str, dict[str, Any]]:
        result = {}
        for mode in MODES:
            success = first_success = positive_slots = reciprocal = 0
            times = []
            for qid in ids:
                clear = sorted(rank for rank, bid in ranked[(qid, mode)]
                               if rank <= TOP_K and labels[(qid, bid)]["clear_fit"] == "1")
                positive_slots += len(clear)
                if clear:
                    success += 1
                    first_success += clear[0] == 1
                    reciprocal += 1 / clear[0]
                times.append(timings[(qid, mode)])
            n = len(ids)
            result[mode] = {
                "top_five_success_count": success,
                "success_at_5": round(success / n, 4),
                "top_one_success_count": first_success,
                "top_one_success_rate": round(first_success / n, 4),
                "strong_precision_at_5": round(positive_slots / (TOP_K * n), 4),
                "mrr_at_5": round(reciprocal / n, 4),
                "warm_p95_ms": round(sorted(times)[math.ceil(0.95 * n) - 1], 3),
            }
        return result

    findings = {}
    for qid in query_map:
        findings[qid] = {}
        for mode in MODES:
            first = next((
                (rank, bid) for rank, bid in sorted(ranked[(qid, mode)])
                if rank <= TOP_K and labels[(qid, bid)]["clear_fit"] == "1"
            ), None)
            findings[qid][mode] = {
                "first_clear_rank": first[0] if first else None,
                "book_id": first[1] if first else None,
                "title": metadata[(qid, first[1])][0] if first else None,
                "book_url": metadata[(qid, first[1])][5] if first else None,
            }
    by_language = {}
    for language in sorted({query.language for query in queries}):
        ids = [query.query_id for query in queries if query.language == language]
        by_language[language] = {"query_count": len(ids), "modes": metrics_for(ids)}
    by_split = {}
    for split in ("development", "holdout"):
        ids = [query.query_id for query in queries if query.split == split]
        if ids:
            by_split[split] = {"query_count": len(ids), "modes": metrics_for(ids)}
    return {
        "assessment": "assistant_not_human", "model_key": spec.key,
        "model_repo": spec.repo, "model_revision": spec.revision,
        "runs_sha256": manifest["runs_sha256"],
        "queries_sha256": manifest["queries_sha256"],
        "labels_sha256": sha256_file(labels_path),
        "query_count": len(queries), "judged_pairs": len(labels),
        "clear_fit_pairs": sum(row["clear_fit"] == "1" for row in labels.values()),
        "basis_counts": dict(sorted(Counter(row["basis"] for row in labels.values()).items())),
        "modes": metrics_for(list(query_map)), "by_language": by_language,
        "by_split": by_split, "query_findings": findings,
        "limits": (
            "Assistant ratings of authored first-five results. Neither model was trained "
            "on these questions. Book contents were not comprehensively reviewed; "
            "real student and human-review quality remains unmeasured."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score assistant-reviewed embedding trials")
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--model", choices=TRIAL_MODELS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score_trial(
        args.queries, args.results_dir, args.labels, TRIAL_MODELS[args.model]
    )
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"model": args.model, "judged_pairs": report["judged_pairs"]}))


if __name__ == "__main__":
    main()
