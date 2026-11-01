import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

import pytest

from archivist.evaluation import (
    EvalCase,
    RunParameters,
    build_eval_report,
    fingerprint_eval_data,
)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def report_inputs(tmp_path: Path):
    run_dir = tmp_path / "run"
    grade_dir = tmp_path / "grades"
    corpus = run_dir / "inputs/corpus"
    corpus.mkdir(parents=True)
    grade_dir.mkdir()

    for name in ("a.md", "b.md"):
        (corpus / name).write_text("Sample evidence", encoding="utf-8")

    cases = [
        EvalCase(
            id="case-001",
            question="Which facts?",
            answerable=True,
            reference_answer="Both facts.",
            expected_sources=["a.md", "b.md"],
        ),
        EvalCase(
            id="case-002",
            question="Which retention period?",
            answerable=False,
            reference_answer="Not specified.",
            expected_sources=[],
        ),
    ]
    cases_path = run_dir / "inputs/cases.json"
    write_json(cases_path, [case.model_dump() for case in cases])

    rows = [
        {
            "id": case.id,
            "question": case.question,
            "answer": "Partial answer." if number == 1 else "Not specified.",
            "retrieved": [{"source": "a.md", "distance": 0.2}],
            "retrieve_seconds": float(number),
            "generate_seconds": float(number * 2),
        }
        for number, case in enumerate(cases, start=1)
    ]
    results_path = run_dir / "results.jsonl"
    write_jsonl(results_path, rows)

    fingerprints = asdict(fingerprint_eval_data(cases_path, corpus))
    parameters = RunParameters(
        chat_variant="test",
        chat_model="test-chat",
        chat_temperature=0.2,
        chat_reasoning_effort="none",
        embedding_model="test-embedding",
        chunk_size=1000,
        chunk_overlap=200,
        k=1,
    )
    write_json(
        run_dir / "manifest.json",
        {
            "schema_version": 1,
            "status": "completed",
            "run_id": "test-run",
            "completed_cases": 2,
            "parameters": parameters.model_dump(),
            "data": fingerprints,
        },
    )

    grades = [
        {
            "id": case.id,
            "question": case.question,
            "answerable": case.answerable,
            "reference_answer_snapshot": case.reference_answer,
            "answer_snapshot": row["answer"],
            "grade": {
                "matches_reference": number == 2,
                "reason": "Stub review.",
            },
        }
        for number, (case, row) in enumerate(zip(cases, rows, strict=True), start=1)
    ]
    write_jsonl(grade_dir / "grades.jsonl", grades)
    write_json(
        grade_dir / "metadata.json",
        {
            "schema_version": 1,
            "status": "completed",
            "source_run_id": "test-run",
            "results_sha256": sha256(results_path.read_bytes()).hexdigest(),
            "data": fingerprints,
            "expected_cases": 2,
            "graded_cases": 2,
            "passed_cases": 1,
            "judge": {"model": "test-judge"},
            "rubric_version": "reference-v1",
        },
    )
    return run_dir, grade_dir


def test_report_uses_correct_denominators_and_mean_timings(report_inputs):
    report = build_eval_report(*report_inputs)

    assert report["metrics"] == {
        "cases": 2,
        "source_recall_cases": 1,
        "mean_source_recall": 0.5,
        "graded_cases": 2,
        "reference_matches": 1,
        "reference_match_rate": 0.5,
        "mean_retrieve_seconds": 1.5,
        "mean_generate_seconds": 3.0,
    }


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("status", "incomplete", "requires completed"),
        ("source_run_id", "other-run", "another answer run"),
        ("results_sha256", "wrong-hash", "does not match the answer file"),
        ("passed_cases", 0, "counts do not match"),
    ],
    ids=["incomplete", "wrong-run", "wrong-answer-hash", "wrong-count"],
)
def test_report_rejects_mismatched_metadata(report_inputs, field, value, message):
    run_dir, grade_dir = report_inputs
    path = grade_dir / "metadata.json"
    metadata = read_json(path)
    metadata[field] = value
    write_json(path, metadata)

    with pytest.raises(ValueError, match=message):
        build_eval_report(run_dir, grade_dir)


def test_report_rejects_changed_input_bytes(report_inputs):
    run_dir, grade_dir = report_inputs
    path = run_dir / "inputs/cases.json"
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="Input fingerprints do not match"):
        build_eval_report(run_dir, grade_dir)


def test_report_rejects_changed_grade_snapshot(report_inputs):
    run_dir, grade_dir = report_inputs
    path = grade_dir / "grades.jsonl"
    rows = read_jsonl(path)
    rows[0]["answer_snapshot"] = "Different answer"
    write_jsonl(path, rows)

    with pytest.raises(ValueError, match="Grade snapshot mismatch"):
        build_eval_report(run_dir, grade_dir)


def test_report_rejects_missing_grade(report_inputs):
    run_dir, grade_dir = report_inputs
    path = grade_dir / "grades.jsonl"
    write_jsonl(path, read_jsonl(path)[:1])

    with pytest.raises(ValueError, match="cover the complete dataset"):
        build_eval_report(run_dir, grade_dir)


@pytest.mark.parametrize(
    "value",
    [-1.0, float("nan"), float("inf"), "1.0", True],
    ids=["negative", "nan", "infinity", "string", "boolean"],
)
def test_report_rejects_invalid_timings(report_inputs, value):
    run_dir, grade_dir = report_inputs
    results_path = run_dir / "results.jsonl"
    rows = read_jsonl(results_path)
    rows[0]["retrieve_seconds"] = value
    write_jsonl(results_path, rows)

    metadata_path = grade_dir / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["results_sha256"] = sha256(results_path.read_bytes()).hexdigest()
    write_json(metadata_path, metadata)

    with pytest.raises(ValueError, match="finite non-negative numbers"):
        build_eval_report(run_dir, grade_dir)
