"""The compact saved run is enough to diagnose known ranking losses."""

from pathlib import Path

import pytest

from libraries_evaluation.miss_audit import audit_misses, classify_miss

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("hybrid_grades", "pooled_grades", "pooled_topics", "expected"),
    [
        ([2, 0], [2], [2], "success"),
        ([1, 0], [2, 1], [2], "ranking_loss"),
        ([1, 0], [1, 0], [2, 1], "reading_need_not_verified"),
        ([0, 1], [0, 1], [1, 0], "no_topic_fit_in_judged_pool"),
    ],
)
def test_classify_miss_distinguishes_known_evidence(
    hybrid_grades, pooled_grades, pooled_topics, expected
):
    assert classify_miss(hybrid_grades, pooled_grades, pooled_topics) == expected


def test_saved_persona_run_has_only_four_known_ranking_losses():
    report = audit_misses(
        ROOT / "evaluation/personas/search-run-99e564e.zip",
        ROOT / "evaluation/personas/ai-labels.csv",
        ROOT / "evaluation/queries/student-personas.jsonl",
    )
    assert report["categories"] == {
        "success": 15,
        "ranking_loss": 4,
        "reading_need_not_verified": 12,
        "no_topic_fit_in_judged_pool": 19,
    }
    assert report["rankable_query_ids"] == [
        "student-18", "student-26", "student-33", "student-39"
    ]
    assert report["judged_pool_ceiling"] == 19
    assert report["review_pairs_without_abstract"] == 133
