from __future__ import annotations

import csv
from pathlib import Path

import pytest

from experiments.acm_paper.rq4_privacy_evaluation.residual_identity_audit import (
    CUES,
    aggregate,
    agreement,
    read_annotations,
    write_template,
)


def _row(image_id: str, score: int = 0) -> dict:
    return {"image_id": image_id, **{cue: score for cue in CUES}, "notes": ""}


def test_template_uses_anonymous_ids(tmp_path: Path):
    path = tmp_path / "audit.csv"
    write_template(path, image_count=3)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["image_id"] for row in rows] == ["E01", "E02", "E03"]


def test_aggregate_counts_possible_and_clear_separately():
    rows = [_row("E01"), _row("E02"), _row("E03")]
    rows[0]["teeth"] = 1
    rows[1]["teeth"] = 2
    rows[1]["lips"] = 2
    summary = aggregate(rows)
    assert summary["cues"]["teeth"] == {
        "any_residual_cases": 2,
        "clearly_visible_cases": 1,
        "rate_any_percent": 66.7,
    }
    assert summary["cues"]["any_identity_relevant_cue"]["any_residual_cases"] == 2


def test_invalid_score_is_rejected(tmp_path: Path):
    path = tmp_path / "audit.csv"
    write_template(path, image_count=1)
    text = path.read_text(encoding="utf-8").replace("E01,,,,,,,,", "E01,3,0,0,0,0,0,0,")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="score must be 0, 1, or 2"):
        read_annotations(path, expected_count=1)


def test_agreement_reports_perfect_match():
    rows = [_row("E01"), _row("E02", score=1), _row("E03", score=2)]
    result = agreement(rows, [dict(row) for row in rows])
    assert result["teeth"]["exact_agreement_percent"] == 100.0
    assert result["teeth"]["cohen_kappa"] == 1.0
