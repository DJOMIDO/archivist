import json
import runpy
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest
from langchain_core.language_models import BaseChatModel

from archivist.config import Settings
from archivist.evaluation import (
    REFERENCE_JUDGE_PROMPT,
    ReferenceGrade,
    fingerprint_eval_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def run_batch(monkeypatch, run_dir: Path):
    monkeypatch.setattr(
        "sys.argv",
        ["judge_batch.py", str(run_dir), "--judge-variant", "offline-test"],
    )
    runpy.run_path(
        str(PROJECT_ROOT / "scripts/judge_batch.py"),
        run_name="__main__",
    )


def read_grade_files(run_dir: Path):
    grade_dir = next((run_dir / "reference-grades").iterdir())
    metadata = json.loads((grade_dir / "metadata.json").read_text(encoding="utf-8"))
    return metadata, read_jsonl(grade_dir / "grades.jsonl")


@pytest.fixture
def grading_run(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    run_dir = tmp_path / "run"
    corpus = run_dir / "inputs/corpus"
    corpus.mkdir(parents=True)
    (corpus / "note.md").write_text("Sample evidence", encoding="utf-8")

    cases = [
        {
            "id": f"case-{number:03d}",
            "question": f"Question {number}?",
            "answerable": True,
            "reference_answer": f"Reference answer {number}",
            "expected_sources": ["note.md"],
        }
        for number in (1, 2)
    ]
    cases_path = run_dir / "inputs/cases.json"
    cases_path.write_text(json.dumps(cases), encoding="utf-8")

    rows = [
        {
            "id": case["id"],
            "question": case["question"],
            "answer": f"Candidate {number}",
        }
        for number, case in enumerate(cases, start=1)
    ]
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    record = {
        "schema_version": 1,
        "run_id": "offline-run",
        "status": "completed",
        "data": asdict(fingerprint_eval_data(cases_path, corpus)),
    }
    (run_dir / "manifest.json").write_text(json.dumps(record), encoding="utf-8")

    settings = Settings(
        _env_file=None,
        chat_model="offline-judge",
        chat_reasoning_effort="none",
        llm_api_key="offline-secret",
    )
    llm = Mock(spec=BaseChatModel)
    monkeypatch.setattr("archivist.config.Settings", lambda: settings)
    monkeypatch.setattr("archivist.qa.get_chat_model", Mock(return_value=llm))
    return run_dir, llm


def test_batch_script_saves_grades_and_provenance(grading_run, monkeypatch):
    run_dir, llm = grading_run
    before = (run_dir / "results.jsonl").read_bytes()
    llm.with_structured_output.return_value.invoke.side_effect = [
        ReferenceGrade(matches_reference=True, reason="First stub verdict."),
        ReferenceGrade(matches_reference=False, reason="Second stub verdict."),
    ]

    run_batch(monkeypatch, run_dir)
    metadata, rows = read_grade_files(run_dir)

    assert metadata["status"] == "completed"
    assert metadata["expected_cases"] == metadata["graded_cases"] == 2
    assert metadata["passed_cases"] == 1
    assert metadata["source_run_id"] == "offline-run"
    assert metadata["data"] == asdict(
        fingerprint_eval_data(
            run_dir / "inputs/cases.json",
            run_dir / "inputs/corpus",
        )
    )
    assert metadata["output_schema"] == ReferenceGrade.model_json_schema()
    assert metadata["results_sha256"] == sha256(before).hexdigest()
    assert metadata["prompt"] == REFERENCE_JUDGE_PROMPT
    assert (
        metadata["prompt_sha256"]
        == sha256(REFERENCE_JUDGE_PROMPT.encode("utf-8")).hexdigest()
    )
    assert metadata["judge"] == {
        "model": "offline-judge",
        "variant": "offline-test",
        "temperature": 0.0,
        "reasoning_effort": "none",
    }
    assert [row["id"] for row in rows] == ["case-001", "case-002"]
    assert [row["answer_snapshot"] for row in rows] == [
        "Candidate 1",
        "Candidate 2",
    ]
    assert [row["grade"]["matches_reference"] for row in rows] == [
        True,
        False,
    ]
    assert "offline-secret" not in json.dumps(metadata)
    assert (run_dir / "results.jsonl").read_bytes() == before


@pytest.mark.parametrize("completed_before_failure", [0, 1])
def test_batch_script_preserves_progress_on_failure(
    grading_run, monkeypatch, completed_before_failure
):
    run_dir, llm = grading_run
    llm.with_structured_output.return_value.invoke.side_effect = [
        ReferenceGrade(
            matches_reference=False,
            reason="A stub verdict that does not match the reference.",
        )
    ] * completed_before_failure + [RuntimeError("judge unavailable")]

    with pytest.raises(RuntimeError, match="judge unavailable"):
        run_batch(monkeypatch, run_dir)

    metadata, rows = read_grade_files(run_dir)

    assert metadata["status"] == "incomplete"
    assert metadata["expected_cases"] == 2
    assert metadata["graded_cases"] == len(rows) == completed_before_failure
    assert metadata["passed_cases"] == 0
    assert [row["id"] for row in rows] == ["case-001"][:completed_before_failure]
    assert [row["grade"]["matches_reference"] for row in rows] == [
        False
    ] * completed_before_failure
