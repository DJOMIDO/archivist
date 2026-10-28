import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel
from langchain_core.vectorstores import VectorStore
from pydantic import ValidationError

from archivist.evaluation import EvalCase, load_eval_cases, run_eval_case


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


class PromptRecorder(BaseCallbackHandler):
    """Capture prompts without contacting a real model."""

    def __init__(self):
        self.prompts = []

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.prompts.extend(prompts)


def test_run_case_records_results_without_leaking_reference(
    tmp_path: Path, sample_case, monkeypatch
):
    case = EvalCase.model_validate(
        {**sample_case, "reference_answer": "REFERENCE_ONLY_SENTINEL"}
    )
    doc = Document(
        page_content="Sample content",
        metadata={"source": str(tmp_path / "note.md")},
    )
    store = Mock(spec=VectorStore)
    store.similarity_search_with_score.return_value = [(doc, 0.25)]

    recorder = PromptRecorder()
    llm = FakeListChatModel(
        responses=["Sample content [1]."],
        callbacks=[recorder],
    )

    ticks = iter([10.0, 12.0, 15.0])
    monkeypatch.setattr("archivist.evaluation.perf_counter", lambda: next(ticks))

    result = run_eval_case(case, store, llm, tmp_path, k=2)

    store.similarity_search_with_score.assert_called_once_with(case.question, k=2)
    assert result.id == case.id
    assert result.question == case.question
    assert result.answer == "Sample content [1]."
    assert len(result.retrieved) == 1
    assert result.retrieved[0].source == "note.md"
    assert result.retrieved[0].distance == 0.25
    assert result.cited_sources == ["note.md"]
    assert result.retrieve_seconds == 2.0
    assert result.generate_seconds == 3.0

    assert len(recorder.prompts) == 1
    prompt = recorder.prompts[0]
    assert case.question in prompt
    assert doc.page_content in prompt
    assert case.reference_answer not in prompt


def test_run_case_with_no_hits_skips_model(tmp_path: Path, sample_case):
    case = EvalCase.model_validate(sample_case)
    store = Mock(spec=VectorStore)
    store.similarity_search_with_score.return_value = []
    llm = FakeListChatModel(responses=[])

    result = run_eval_case(case, store, llm, tmp_path, k=2)

    assert result.retrieved == []
    assert result.cited_sources == []
    assert result.answer == "I couldn't find this in your documents."
