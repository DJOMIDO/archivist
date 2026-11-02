import json
from dataclasses import asdict
from pathlib import Path

import pytest

from archivist.evaluation import (
    RunParameters,
    fingerprint_eval_data,
    load_indexed_run,
)


def write_manifest(run_dir: Path, record: dict) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(record), encoding="utf-8")


@pytest.fixture
def current_software():
    return {
        "current_python": "test-python",
        "current_packages": {"example": "1.0"},
    }


@pytest.fixture
def indexed_run(tmp_path: Path, current_software):
    corpus = tmp_path / "inputs/corpus"
    corpus.mkdir(parents=True)
    (corpus / "note.md").write_text("Sample content", encoding="utf-8")

    cases_path = tmp_path / "inputs/cases.json"
    cases_path.write_text("[]", encoding="utf-8")

    index = tmp_path / "chroma/chroma.sqlite3"
    index.parent.mkdir()
    index.touch()

    parameters = RunParameters(
        chat_variant="test",
        chat_model="example-chat",
        chat_temperature=0.2,
        chat_reasoning_effort="none",
        embedding_model="example-embedding",
        chunk_size=1000,
        chunk_overlap=200,
        k=4,
    )
    record = {
        "schema_version": 1,
        "status": "indexed",
        "parameters": parameters.model_dump(mode="json"),
        "data": asdict(fingerprint_eval_data(cases_path, corpus)),
        "software": {
            "python": current_software["current_python"],
            "packages": current_software["current_packages"],
        },
    }
    write_manifest(tmp_path, record)
    return tmp_path, record


def test_load_matching_indexed_run(indexed_run, current_software):
    run_dir, expected = indexed_run

    record, parameters = load_indexed_run(run_dir, **current_software)

    assert record == expected
    assert parameters == RunParameters.model_validate(expected["parameters"])


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "prepared"},
        {"status": "running"},
        {"status": "completed"},
        {"schema_version": 2},
    ],
    ids=["prepared", "running", "completed", "unsupported-schema"],
)
def test_reject_ineligible_run(indexed_run, current_software, changes):
    run_dir, record = indexed_run
    record.update(changes)
    write_manifest(run_dir, record)

    with pytest.raises(ValueError, match="Expected an indexed run"):
        load_indexed_run(run_dir, **current_software)


@pytest.mark.parametrize(
    "relative_path",
    ["inputs/cases.json", "inputs/corpus/note.md"],
    ids=["changed-cases", "changed-document"],
)
def test_reject_changed_snapshot(indexed_run, current_software, relative_path):
    run_dir, _ = indexed_run
    path = run_dir / relative_path
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="snapshot no longer matches"):
        load_indexed_run(run_dir, **current_software)


def test_reject_missing_index(indexed_run, current_software):
    run_dir, _ = indexed_run
    (run_dir / "chroma/chroma.sqlite3").unlink()

    with pytest.raises(FileNotFoundError, match="Prepared index is missing"):
        load_indexed_run(run_dir, **current_software)


@pytest.mark.parametrize(
    "changes",
    [
        {"current_python": "other-python"},
        {"current_packages": {"example": "2.0"}},
    ],
    ids=["python-version", "package-version"],
)
def test_reject_changed_software(indexed_run, current_software, changes):
    run_dir, _ = indexed_run
    current_software.update(changes)

    with pytest.raises(ValueError, match="Software versions changed"):
        load_indexed_run(run_dir, **current_software)


def test_reject_existing_results_without_modifying_them(indexed_run, current_software):
    run_dir, _ = indexed_run
    results = run_dir / "results.jsonl"
    results.write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already has results"):
        load_indexed_run(run_dir, **current_software)

    assert results.read_text(encoding="utf-8") == "existing\n"
