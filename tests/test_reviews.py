import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archivist.evaluation import load_reviews


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def review_files(tmp_path: Path):
    results_path = tmp_path / "run.jsonl"
    review_path = tmp_path / "reviews.json"
    answer = "  Sample content [1].  "

    row = {
        "id": "case-001",
        "answer": answer,
        "cited_sources": ["note.md"],
    }
    results_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    data = {
        "run_file": "run.jsonl",
        "rubric_version": "1",
        "reviews": [
            {
                "id": "case-001",
                "answer_snapshot": answer,
                "cited_sources_snapshot": ["note.md"],
                "correctness": True,
                "completeness": True,
                "citations": True,
                "reason": "Supported by note.md.",
            }
        ],
    }
    write_json(review_path, data)
    return review_path, results_path, data


def test_load_reviews_preserves_snapshots(review_files):
    review_path, results_path, data = review_files

    loaded = load_reviews(review_path, results_path)

    assert len(loaded.reviews) == 1
    review = loaded.reviews[0]
    assert review.answer_snapshot == data["reviews"][0]["answer_snapshot"]
    assert review.cited_sources_snapshot == ["note.md"]
    assert review.correctness is True


@pytest.mark.parametrize(
    "changes",
    [
        {"correctness": "true"},
        {"completeness": 1},
        {"citations": None},
        {"reason": "   "},
    ],
    ids=["string-bool", "integer-bool", "null-bool", "blank-reason"],
)
def test_reject_invalid_review_fields(review_files, changes):
    review_path, results_path, data = review_files
    data["reviews"][0].update(changes)
    write_json(review_path, data)

    with pytest.raises(ValidationError):
        load_reviews(review_path, results_path)


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"id": "unknown"}, "Unknown review ID"),
        ({"answer_snapshot": "Changed answer"}, "Answer snapshot mismatch"),
        (
            {"cited_sources_snapshot": ["other.md"]},
            "Citation snapshot mismatch",
        ),
    ],
    ids=["unknown-id", "changed-answer", "changed-citations"],
)
def test_reject_review_mismatches(review_files, changes, message):
    review_path, results_path, data = review_files
    data["reviews"][0].update(changes)
    write_json(review_path, data)

    with pytest.raises(ValueError, match=message):
        load_reviews(review_path, results_path)


def test_reject_duplicate_reviews(review_files):
    review_path, results_path, data = review_files
    data["reviews"].append(data["reviews"][0].copy())
    write_json(review_path, data)

    with pytest.raises(ValueError, match="Duplicate review ID"):
        load_reviews(review_path, results_path)


def test_reject_wrong_run_file(review_files):
    review_path, results_path, data = review_files
    data["run_file"] = "other.jsonl"
    write_json(review_path, data)

    with pytest.raises(ValueError, match="run_file does not match"):
        load_reviews(review_path, results_path)
