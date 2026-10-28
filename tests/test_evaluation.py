import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archivist.evaluation import load_eval_cases


@pytest.fixture
def sample_case():
    return {
        "id": "case-001",
        "question": "What is documented?",
        "answerable": True,
        "reference_answer": "Sample content",
        "expected_sources": ["note.md"],
    }


@pytest.fixture
def dataset_paths(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("Sample content", encoding="utf-8")
    return tmp_path / "cases.json", corpus


def write_cases(path: Path, cases: list[dict]) -> None:
    path.write_text(json.dumps(cases), encoding="utf-8")


def test_load_valid_cases(dataset_paths, sample_case):
    path, corpus = dataset_paths
    unanswered = {
        **sample_case,
        "id": "case-002",
        "answerable": False,
        "reference_answer": "Not documented",
        "expected_sources": [],
    }
    write_cases(path, [sample_case, unanswered])

    cases = load_eval_cases(path, corpus)

    assert len(cases) == 2
    assert cases[0].id == "case-001"
    assert cases[0].expected_sources == ["note.md"]
    assert cases[1].answerable is False


@pytest.mark.parametrize(
    "changes",
    [
        {"answerable": "false"},
        {"question": "   "},
        {"unexpected": 1},
        {"expected_sources": []},
    ],
    ids=["string-bool", "blank-question", "extra-field", "missing-evidence"],
)
def test_reject_invalid_fields(dataset_paths, sample_case, changes):
    path, corpus = dataset_paths
    write_cases(path, [{**sample_case, **changes}])

    with pytest.raises(ValidationError):
        load_eval_cases(path, corpus)


def test_reject_duplicate_ids(dataset_paths, sample_case):
    path, corpus = dataset_paths
    write_cases(path, [sample_case, sample_case])

    with pytest.raises(ValueError, match="Duplicate ID"):
        load_eval_cases(path, corpus)


def test_reject_missing_source(dataset_paths, sample_case):
    path, corpus = dataset_paths
    sample_case["expected_sources"] = ["missing.md"]
    write_cases(path, [sample_case])

    with pytest.raises(FileNotFoundError, match="missing source"):
        load_eval_cases(path, corpus)


def test_reject_empty_dataset(dataset_paths):
    path, corpus = dataset_paths
    write_cases(path, [])

    with pytest.raises(ValidationError):
        load_eval_cases(path, corpus)
