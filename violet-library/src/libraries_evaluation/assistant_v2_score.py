"""Score clearly useful assistant judgments without changing human-review sheets."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from libraries_evaluation.queries import load_queries
from libraries_evaluation.review_packet import DOAB_MODES, TOP_K, _read_packet

LABEL_FIELDS = ("query_id", "book_id", "clear_fit", "basis", "evidence_url")
BASES = {"prior_assistant", "new_preview", "source_page", "language_recheck"}


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_labels(
    labels_path: Path, expected: set[tuple[str, str]]
) -> dict[tuple[str, str], dict[str, str]]:
    labels = {}
    with Path(labels_path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != LABEL_FIELDS:
            raise ValueError("Assistant labels have unexpected columns")
        for row in reader:
            key = row["query_id"], row["book_id"]
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Assistant labels contain a malformed row")
            if key not in expected or key in labels:
                raise ValueError("Assistant labels contain an unknown or duplicate pair")
            if row["clear_fit"] not in {"0", "1"} or row["basis"] not in BASES:
                raise ValueError("Assistant labels contain an invalid judgment")
            if row["basis"] == "source_page" and not row["evidence_url"].startswith("https://"):
                raise ValueError("Source-page judgment needs an HTTPS evidence link")
            labels[key] = row
    if set(labels) != expected:
        raise ValueError(f"Assistant labels are missing {len(expected - set(labels))} pairs")
    return labels


def score_assistant_packet(
    queries_path: Path, packet_dir: Path, archive: Path, labels_path: Path,
    *, miss_report: Path | None = None,
) -> dict[str, Any]:
    """Validate full assistant labels, then score the frozen top-five rankings."""
    manifest, sheets, source_rows = _read_packet(
        queries_path, packet_dir, archive, miss_report
    )
    labels = _load_labels(labels_path, set(sheets))
    queries = {query.query_id: query for query in load_queries(queries_path)}
    modes = DOAB_MODES if manifest["kind"] == "doab" else ("textbook",)
    ranked: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    timings: dict[tuple[str, str], float] = {}
    for row in source_rows:
        rank = int(row["rank"])
        if rank > TOP_K:
            continue
        mode = row["mode"] if manifest["kind"] == "doab" else "textbook"
        key = row["query_id"], mode
        ranked[key].append((rank, row["book_id"]))
        if rank == 1 and manifest["kind"] == "doab":
            timings[key] = float(row["latency_ms"])

    def metrics_for(query_ids: list[str]) -> dict[str, dict[str, Any]]:
        metrics = {}
        for mode in modes:
            success = top_one = strong_books = reciprocal = 0
            latencies = []
            for qid in query_ids:
                books = sorted(ranked[(qid, mode)])
                clear_ranks = [
                    rank for rank, book_id in books if labels[(qid, book_id)]["clear_fit"] == "1"
                ]
                strong_books += len(clear_ranks)
                if clear_ranks:
                    success += 1
                    first = min(clear_ranks)
                    top_one += first == 1
                    reciprocal += 1 / first
                if manifest["kind"] == "doab":
                    latencies.append(timings[(qid, mode)])
            n = len(query_ids)
            ordered = sorted(latencies)
            metrics[mode] = {
                "top_five_success_count": success,
                "success_at_5": round(success / n, 4),
                "top_one_success_count": top_one,
                "top_one_success_rate": round(top_one / n, 4),
                "strong_precision_at_5": round(strong_books / (TOP_K * n), 4),
                "mrr_at_5": round(reciprocal / n, 4),
                "warm_p95_ms": (
                    round(ordered[math.ceil(0.95 * n) - 1], 3) if ordered else None
                ),
            }
        return metrics

    by_language = {}
    for language in sorted({queries[qid].language for qid in manifest["query_ids"]}):
        ids = [qid for qid in manifest["query_ids"] if queries[qid].language == language]
        by_language[language] = {"query_count": len(ids), "modes": metrics_for(ids)}
    by_split = {}
    for split in ("development", "holdout"):
        ids = [qid for qid in manifest["query_ids"] if queries[qid].split == split]
        if ids:
            by_split[split] = {"query_count": len(ids), "modes": metrics_for(ids)}
    query_findings = {}
    for qid in manifest["query_ids"]:
        query_findings[qid] = {}
        for mode in modes:
            first = next((
                (rank, book_id) for rank, book_id in sorted(ranked[(qid, mode)])
                if labels[(qid, book_id)]["clear_fit"] == "1"
            ), None)
            query_findings[qid][mode] = {
                "first_clear_rank": first[0] if first else None,
                "book_id": first[1] if first else None,
                "title": sheets[(qid, first[1])]["title"] if first else None,
                "book_url": sheets[(qid, first[1])]["book_url"] if first else None,
            }
    question_kind = (
        "These authored development questions "
        if "development" in by_split else "These questions "
    )
    return {
        "assessment": "assistant_not_human",
        "kind": manifest["kind"],
        "source_archive_sha256": manifest["source_archive_sha256"],
        "queries_sha256": manifest["queries_sha256"],
        "labels_sha256": _sha_file(labels_path),
        "query_count": len(manifest["query_ids"]),
        "judged_pairs": len(labels),
        "basis_counts": dict(sorted(Counter(row["basis"] for row in labels.values()).items())),
        "clear_fit_pairs": sum(row["clear_fit"] == "1" for row in labels.values()),
        "missing_description_pairs": sum(not row["description_excerpt"] for row in sheets.values()),
        "modes": metrics_for(manifest["query_ids"]),
        "by_language": by_language,
        "by_split": by_split,
        "query_findings": query_findings,
        "limits": (
            "Assistant judgments of frozen top-five results. "
            + question_kind
            + "do not establish student-use quality; book contents were not comprehensively "
            "reviewed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score separate assistant judgments of v2 search")
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--miss-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score_assistant_packet(
        args.queries, args.packet_dir, args.archive, args.labels,
        miss_report=args.miss_report,
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"kind": report["kind"], "query_count": report["query_count"],
                      "judged_pairs": report["judged_pairs"]}))


if __name__ == "__main__":
    main()
