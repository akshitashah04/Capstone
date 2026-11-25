"""Validate fictional student scenarios and export frozen search questions."""

import argparse
import json
from collections import Counter
from pathlib import Path

from libraries_evaluation.queries import LANGUAGE, QUERY_ID, load_queries

PERSONA_FIELDS = {
    "persona_id", "level", "major", "language", "learning_goal", "reading_need", "query"
}
LEVELS = {"undergraduate", "graduate"}


def load_personas(path: Path) -> list[dict[str, str]]:
    """Read the small anonymous scenario file, rejecting changed or duplicate records."""
    personas: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid persona JSON on line {line_number}") from error
        if not isinstance(row, dict) or set(row) != PERSONA_FIELDS:
            raise ValueError(f"Persona line {line_number} has unexpected fields")
        if any(not isinstance(value, str) or not value.strip() for value in row.values()):
            raise ValueError(f"Persona line {line_number} has an empty or invalid value")
        if not QUERY_ID.fullmatch(row["persona_id"]):
            raise ValueError(f"Persona line {line_number} has an invalid ID")
        if row["persona_id"] in seen:
            raise ValueError(f"Duplicate persona ID: {row['persona_id']}")
        if row["level"] not in LEVELS or not LANGUAGE.fullmatch(row["language"]):
            raise ValueError(f"Persona line {line_number} has invalid level or language")
        seen.add(row["persona_id"])
        personas.append(row)
    if not personas:
        raise ValueError("Persona file is empty")
    return personas


def export_persona_queries(source: Path, output: Path) -> None:
    """Freeze the 50 scenarios as ordinary development questions for the collector."""
    personas = load_personas(source)
    levels = Counter(persona["level"] for persona in personas)
    if len(personas) != 50 or levels != {"undergraduate": 25, "graduate": 25}:
        raise ValueError("This diagnostic requires 25 undergraduate and 25 graduate personas")
    if len({persona["major"] for persona in personas}) != 50:
        raise ValueError("Every persona must have a distinct major or program")
    output = Path(output)
    with output.open("w", encoding="utf-8") as stream:
        for persona in personas:
            row = {
                "query_id": persona["persona_id"],
                "text": persona["query"],
                "language": persona["language"],
                "intent": "topic",
                "split": "development",
            }
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    load_queries(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export frozen synthetic student questions")
    parser.add_argument("--personas", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_persona_queries(args.personas, args.output)
    print(f"Exported {len(load_queries(args.output))} fictional student queries")


if __name__ == "__main__":
    main()
