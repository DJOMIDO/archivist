import json
import runpy
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel

from archivist.config import Settings
from archivist.evaluation import fingerprint_eval_data, run_eval_case
from archivist.registry import get_index_profile

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_script(monkeypatch, name: str, *arguments: str):
    monkeypatch.setattr("sys.argv", [name, *arguments])
    runpy.run_path(
        str(PROJECT_ROOT / "scripts" / name),
        run_name="__main__",
    )


def read_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def prepare_run(monkeypatch) -> Path:
    run_script(
        monkeypatch,
        "prepare_eval_run.py",
        "--chat-variant",
        "offline-test",
    )
    return next(Path("storage/eval-runs").iterdir())


@pytest.fixture
def offline_environment(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    corpus = Path("evals/corpus")
    corpus.mkdir(parents=True)
    (corpus / "note.md").write_text(
        "Backups exclude the vector index.", encoding="utf-8"
    )
    cases = [
        {
            "id": f"case-{number:03d}",
            "question": "Do backups include the vector index?",
            "answerable": True,
            "reference_answer": "No, backups exclude the vector index.",
            "expected_sources": ["note.md"],
        }
        for number in (1, 2)
    ]
    Path("evals/cases.json").write_text(json.dumps(cases), encoding="utf-8")

    settings = Settings(
        _env_file=None,
        chat_model="test-chat",
        chat_temperature=0.2,
        chat_reasoning_effort="none",
        embedding_model="test-embedding",
        chunk_size=1000,
        chunk_overlap=200,
    )
    monkeypatch.setattr("archivist.config.Settings", lambda: settings)
    monkeypatch.setattr(
        "archivist.indexing.get_embeddings",
        Mock(return_value=DeterministicFakeEmbedding(size=16)),
    )
    chat_factory = Mock(
        return_value=FakeListChatModel(
            responses=["Backups exclude the vector index [1]."]
        )
    )
    monkeypatch.setattr("archivist.qa.get_chat_model", chat_factory)
    return settings, chat_factory


def test_prepare_and_execute_snapshot(monkeypatch, offline_environment):
    settings, chat_factory = offline_environment
    run_dir = prepare_run(monkeypatch)
    prepared = read_manifest(run_dir)

    assert prepared["status"] == "indexed"
    assert prepared["documents"] == prepared["chunks"] == 1
    assert prepared["cases"] == 2
    assert (run_dir / "chroma/chroma.sqlite3").is_file()

    Path("evals/corpus/note.md").write_text(
        "Changed original document.", encoding="utf-8"
    )
    Path("evals/cases.json").write_text("changed original cases", encoding="utf-8")
    settings.embedding_model = "ignored-current-embedding"
    settings.chat_model = "ignored-current-model"
    settings.chat_temperature = 0.9

    run_script(monkeypatch, "run_eval.py", str(run_dir))

    completed = read_manifest(run_dir)
    rows = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert completed["status"] == "completed"
    assert completed["completed_cases"] == len(rows) == 2
    assert [row["id"] for row in rows] == ["case-001", "case-002"]
    assert all(row["cited_sources"] == ["note.md"] for row in rows)

    actual = fingerprint_eval_data(
        run_dir / "inputs/cases.json",
        run_dir / "inputs/corpus",
    )
    assert asdict(actual) == prepared["data"]
    chat_factory.assert_called_once_with(
        "test-chat",
        settings.llm_base_url,
        settings.llm_api_key,
        0.2,
        "none",
    )


def test_execution_failure_preserves_completed_rows(monkeypatch, offline_environment):
    run_dir = prepare_run(monkeypatch)

    def fail_on_second_case(case, **kwargs):
        if case.id == "case-002":
            raise RuntimeError("simulated generation failure")
        return run_eval_case(case, **kwargs)

    monkeypatch.setattr(
        "archivist.evaluation.run_eval_case",
        fail_on_second_case,
    )
    with pytest.raises(RuntimeError, match="simulated generation failure"):
        run_script(monkeypatch, "run_eval.py", str(run_dir))

    record = read_manifest(run_dir)
    rows = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert record["status"] == "running"
    assert "finished_at" not in record
    assert [row["id"] for row in rows] == ["case-001"]


def test_indexing_failure_is_not_marked_indexed(monkeypatch, offline_environment):
    monkeypatch.setattr(
        "archivist.indexing.get_embeddings",
        Mock(side_effect=RuntimeError("simulated embedding failure")),
    )
    with pytest.raises(RuntimeError, match="simulated embedding failure"):
        prepare_run(monkeypatch)

    run_dir = next(Path("storage/eval-runs").iterdir())
    assert read_manifest(run_dir)["status"] == "prepared"
    assert not (run_dir / "results.jsonl").exists()


def test_prepare_saves_profile_matching_recorded_parameters(
    monkeypatch, offline_environment
):
    settings, _ = offline_environment
    run_dir = prepare_run(monkeypatch)
    record = read_manifest(run_dir)

    assert record["status"] == "indexed"
    registry_path = run_dir / record["paths"]["registry"]
    assert registry_path.is_file()

    with closing(sqlite3.connect(registry_path)) as registry:
        profile = get_index_profile(registry)

    assert profile is not None
    assert profile.embedding_model == record["parameters"]["embedding_model"]
    assert profile.chunk_size == record["parameters"]["chunk_size"]
    assert profile.chunk_overlap == record["parameters"]["chunk_overlap"]
    assert profile.embedding_base_url == settings.llm_base_url
    assert profile.python == record["software"]["python"]


def test_prepare_profile_failure_stops_before_ingestion(
    monkeypatch, offline_environment
):
    guard = Mock(side_effect=ValueError("simulated incompatible profile"))
    ingest = Mock(side_effect=AssertionError("ingest should not run"))
    monkeypatch.setattr("archivist.pipeline.ensure_index_compatible", guard)
    monkeypatch.setattr("archivist.pipeline.ingest", ingest)

    with pytest.raises(ValueError, match="simulated incompatible profile"):
        prepare_run(monkeypatch)

    guard.assert_called_once()
    ingest.assert_not_called()

    run_dir = next(Path("storage/eval-runs").iterdir())
    record = read_manifest(run_dir)
    assert record["status"] == "prepared"
    assert "documents" not in record
    assert "chunks" not in record
    assert not (run_dir / "results.jsonl").exists()

    with closing(sqlite3.connect(run_dir / record["paths"]["registry"])) as registry:
        assert get_index_profile(registry) is None
        assert registry.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("scenario", "expected_error"),
    [
        ("missing_registry", "Cannot read the evaluation index registry"),
        ("missing_profile", "Index profile is missing"),
        ("changed_model", "Query embedding configuration does not match the index"),
        ("changed_endpoint", "Query embedding configuration does not match the index"),
    ],
)
def test_query_guard_failure_preserves_indexed_run(
    monkeypatch, offline_environment, scenario, expected_error
):
    settings, _ = offline_environment
    run_dir = prepare_run(monkeypatch)
    manifest = run_dir / "manifest.json"
    registry_path = run_dir / "registry.sqlite3"

    if scenario == "missing_registry":
        registry_path.unlink()
    elif scenario == "missing_profile":
        with closing(sqlite3.connect(registry_path)) as registry, registry:
            registry.execute("DELETE FROM index_profile")
    elif scenario == "changed_model":
        record = read_manifest(run_dir)
        record["parameters"]["embedding_model"] = "other-embedding"
        manifest.write_text(json.dumps(record), encoding="utf-8")
    else:
        settings.llm_base_url = "http://localhost:9999/v1"

    manifest_before = manifest.read_bytes()
    registry_before = registry_path.read_bytes() if registry_path.exists() else None
    factories = []
    for name in (
        "archivist.indexing.get_embeddings",
        "archivist.indexing.get_vector_store",
        "archivist.qa.get_chat_model",
    ):
        factory = Mock(side_effect=AssertionError(f"{name} should not run"))
        monkeypatch.setattr(name, factory)
        factories.append(factory)

    with pytest.raises(ValueError, match=expected_error):
        run_script(monkeypatch, "run_eval.py", str(run_dir))

    assert manifest.read_bytes() == manifest_before
    assert read_manifest(run_dir)["status"] == "indexed"
    assert not (run_dir / "results.jsonl").exists()
    if registry_before is None:
        assert not registry_path.exists()
    else:
        assert registry_path.read_bytes() == registry_before
    for factory in factories:
        factory.assert_not_called()
