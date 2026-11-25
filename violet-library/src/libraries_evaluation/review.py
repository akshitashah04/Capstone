"""Prepare and validate small, shared human-review sheets without an index."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from libraries_evaluation.queries import EvaluationQuery, load_queries
from libraries_evaluation.schema import REVIEW_FIELDS, SHEET_FIELDS

GRADES = {"", "0", "1", "2"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"Unexpected columns in {path}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"Malformed CSV row in {path}")
    return rows


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _pair_sha256(pairs: set[tuple[str, str]]) -> str:
    data = "".join(f"{query_id}\0{book_id}\n" for query_id, book_id in sorted(pairs))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _metadata_sha256(rows: dict[tuple[str, str], dict[str, str]]) -> str:
    metadata = [
        {field: rows[key][field] for field in SHEET_FIELDS if field != "relevance"}
        for key in sorted(rows)
    ]
    data = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _compact_text(value: str) -> str:
    return " ".join(value.split())


def _sheet_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "query_id": row["query_id"],
        "query_text": row["query_text"],
        "book_id": row["book_id"],
        "title": _compact_text(row["title"]),
        "book_url": row["book_url"],
        "abstract_excerpt": _compact_text(row["abstract_excerpt"])[:250],
        "relevance": "",
    }


def _read_source_run(
    queries_path: Path, run_dir: Path, queries: list[EvaluationQuery]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("query_count") != len(queries):
        raise ValueError("Source run has an unsupported schema or query count")
    if manifest.get("queries_sha256") != _sha256_file(queries_path):
        raise ValueError("Source run does not match the question file")
    review_path = run_dir / "review.csv"
    if manifest.get("review_sha256") != _sha256_file(review_path):
        raise ValueError("Source review checksum does not match the run manifest")
    rows = _read_csv(review_path, REVIEW_FIELDS)
    if manifest.get("candidate_count") != len(rows):
        raise ValueError("Source run candidate count changed")
    by_id = {query.query_id: query for query in queries}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        query = by_id.get(row["query_id"])
        key = (row["query_id"], row["book_id"])
        if query is None or row["query_text"] != query.text or not row["book_id"]:
            raise ValueError("Source review has an unknown question or book")
        if key in seen or row["relevance"].strip():
            raise ValueError("Source review contains duplicate or pre-judged pairs")
        seen.add(key)
    return manifest, rows


def initialize_review(
    queries_path: Path, run_dir: Path, review_dir: Path, *, source_run_id: int | None = None
) -> dict[str, Any]:
    """Create one blinded, ungraded CSV per question from a verified pilot run."""
    queries_path, run_dir, review_dir = map(Path, (queries_path, run_dir, review_dir))
    queries = load_queries(queries_path)
    source, source_rows = _read_source_run(queries_path, run_dir, queries)
    sheets = {_query.query_id: [] for _query in queries}
    for row in source_rows:
        sheets[row["query_id"]].append(_sheet_row(row))
    all_rows = {
        (row["query_id"], row["book_id"]): row
        for rows in sheets.values()
        for row in rows
    }
    manifest = {
        "schema_version": 1,
        "source_run_id": source_run_id,
        "source_review_sha256": source["review_sha256"],
        "queries_sha256": source["queries_sha256"],
        "index_revision": source["index_revision"],
        "query_ids": [query.query_id for query in queries],
        "candidate_count": len(all_rows),
        "pair_sha256": _pair_sha256(set(all_rows)),
        "metadata_sha256": _metadata_sha256(all_rows),
    }
    review_dir.mkdir(parents=True, exist_ok=False)
    for query in queries:
        rows = sorted(sheets[query.query_id], key=lambda row: row["book_id"])
        _write_csv(review_dir / f"{query.query_id}.csv", SHEET_FIELDS, rows)
    (review_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _read_sheets(
    queries_path: Path, review_dir: Path
) -> tuple[dict[str, Any], list[EvaluationQuery], dict[tuple[str, str], dict[str, str]]]:
    queries = load_queries(queries_path)
    manifest = json.loads((review_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("queries_sha256") != _sha256_file(
        queries_path
    ):
        raise ValueError("Review manifest does not match the question file")
    if manifest.get("query_ids") != [query.query_id for query in queries]:
        raise ValueError("Review manifest question IDs changed")
    expected_files = {f"{query.query_id}.csv" for query in queries}
    actual_files = {path.name for path in review_dir.glob("*.csv")}
    if actual_files != expected_files:
        raise ValueError("Review sheets have missing or extra question files")
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for query in queries:
        for row in _read_csv(review_dir / f"{query.query_id}.csv", SHEET_FIELDS):
            key = (row["query_id"], row["book_id"])
            if key[0] != query.query_id or row["query_text"] != query.text or not key[1]:
                raise ValueError("Review sheet has an unknown question or book")
            if key in rows:
                raise ValueError("Review sheet has a duplicate question–book pair")
            if row["relevance"] not in GRADES:
                raise ValueError(f"Invalid relevance grade for {key[0]}/{key[1]}")
            rows[key] = row
    if len(rows) != manifest.get("candidate_count") or _pair_sha256(set(rows)) != manifest.get(
        "pair_sha256"
    ):
        raise ValueError("Review sheet candidate pool changed")
    if _metadata_sha256(rows) != manifest.get("metadata_sha256"):
        raise ValueError("Review sheet book metadata changed")
    return manifest, queries, rows


def review_progress(queries_path: Path, review_dir: Path) -> dict[str, Any]:
    """Count genuine human grades while allowing unfinished sheets."""
    manifest, queries, rows = _read_sheets(Path(queries_path), Path(review_dir))
    by_query = {}
    for query in queries:
        query_rows = [row for key, row in rows.items() if key[0] == query.query_id]
        graded = sum(bool(row["relevance"]) for row in query_rows)
        by_query[query.query_id] = {
            "candidate_count": len(query_rows),
            "graded_count": graded,
            "remaining_count": len(query_rows) - graded,
        }
    graded_count = sum(bool(row["relevance"]) for row in rows.values())
    return {
        "source_run_id": manifest["source_run_id"],
        "index_revision": manifest["index_revision"],
        "query_count": len(queries),
        "candidate_count": len(rows),
        "graded_count": graded_count,
        "remaining_count": len(rows) - graded_count,
        "complete": graded_count == len(rows),
        "by_query": by_query,
    }


def format_progress_markdown(progress: dict[str, Any]) -> str:
    """Render counts for a GitHub Actions job summary."""
    lines = [
        "# Human book-review progress",
        "",
        f"**{progress['graded_count']} / {progress['candidate_count']}** pairs graded. "
        f"**{progress['remaining_count']}** remain.",
        "",
        "| Question | Graded | Total |",
        "| --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {query_id} | {counts['graded_count']} | {counts['candidate_count']} |"
        for query_id, counts in progress["by_query"].items()
    )
    lines.extend(
        ["", "Relevance metrics are withheld until every pair has a human grade.", ""]
    )
    return "\n".join(lines)


def assemble_judgments(
    queries_path: Path, review_dir: Path, run_dir: Path, output_path: Path
) -> bool:
    """Overlay complete grades onto a fresh matching cloud run; return False if unfinished."""
    queries_path, review_dir, run_dir, output_path = map(
        Path, (queries_path, review_dir, run_dir, output_path)
    )
    output_path.unlink(missing_ok=True)
    manifest, queries, sheets = _read_sheets(queries_path, review_dir)
    source, source_rows = _read_source_run(queries_path, run_dir, queries)
    if source["index_revision"] != manifest["index_revision"]:
        raise ValueError("Fresh cloud run uses a different index revision")
    fresh = {(row["query_id"], row["book_id"]): _sheet_row(row) for row in source_rows}
    if set(fresh) != set(sheets) or _pair_sha256(set(fresh)) != manifest["pair_sha256"]:
        raise ValueError("Fresh cloud candidate pool changed")
    if _metadata_sha256(fresh) != manifest["metadata_sha256"]:
        raise ValueError("Fresh cloud candidate pool metadata changed")
    if any(not row["relevance"] for row in sheets.values()):
        return False
    judged = []
    for row in source_rows:
        judged.append({**row, "relevance": sheets[(row["query_id"], row["book_id"])]["relevance"]})
    _write_csv(output_path, REVIEW_FIELDS, judged)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage small human review sheets")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create ungraded sheets from a verified run")
    init.add_argument("--queries", type=Path, required=True)
    init.add_argument("--run-dir", type=Path, required=True)
    init.add_argument("--review-dir", type=Path, required=True)
    init.add_argument("--source-run-id", type=int)
    progress = commands.add_parser("progress", help="Validate sheets and count grades")
    progress.add_argument("--queries", type=Path, required=True)
    progress.add_argument("--review-dir", type=Path, required=True)
    progress.add_argument("--summary", type=Path)
    assemble = commands.add_parser("assemble", help="Create full judgments only if complete")
    assemble.add_argument("--queries", type=Path, required=True)
    assemble.add_argument("--review-dir", type=Path, required=True)
    assemble.add_argument("--run-dir", type=Path, required=True)
    assemble.add_argument("--output", type=Path, required=True)
    assemble.add_argument("--summary", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        result = initialize_review(
            args.queries, args.run_dir, args.review_dir, source_run_id=args.source_run_id
        )
        print(json.dumps({"candidate_count": result["candidate_count"]}))
        return
    result = review_progress(args.queries, args.review_dir)
    if args.summary:
        args.summary.write_text(format_progress_markdown(result), encoding="utf-8")
    if args.command == "assemble":
        result["assembled"] = assemble_judgments(
            args.queries, args.review_dir, args.run_dir, args.output
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
