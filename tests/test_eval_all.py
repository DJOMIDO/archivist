import json
import os
import runpy
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import BaseChatModel, FakeListChatModel

from archivist.config import Settings
from archivist.evaluation import ReferenceGrade

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRY_ARGS = [
    "eval_all.py",
    "--chat-model",
    "candidate-test",
    "--chat-variant",
    "offline-candidate",
    "--judge-model",
    "judge-test",
    "--judge-variant",
    "offline-judge",
]


def run_entry(monkeypatch):
    monkeypatch.setattr(sys, "argv", ENTRY_ARGS.copy())
    runpy.run_path(
        str(PROJECT_ROOT / "scripts/eval_all.py"),
        run_name="__main__",
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def offline_models(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    corpus = Path("evals/corpus")
    corpus.mkdir(parents=True)
    (corpus / "note.md").write_text("Sample evidence.", encoding="utf-8")
    cases = [
        {
            "id": f"case-{number:03d}",
            "question": "What is documented?",
            "answerable": True,
            "reference_answer": "Sample evidence.",
            "expected_sources": ["note.md"],
        }
        for number in (1, 2)
    ]
    Path("evals/cases.json").write_text(json.dumps(cases), encoding="utf-8")

    def make_settings():
        return Settings(
            _env_file=None,
            chat_temperature=0.2,
            chat_reasoning_effort="none",
            embedding_model="offline-embedding",
            chunk_size=1000,
            chunk_overlap=200,
        )

    monkeypatch.setattr("archivist.config.Settings", make_settings)
    monkeypatch.setattr(
        "archivist.indexing.get_embeddings",
        Mock(return_value=DeterministicFakeEmbedding(size=16)),
    )

    candidate = FakeListChatModel(responses=["Sample evidence [1]."])
    judge = Mock(spec=BaseChatModel)
    judge.with_structured_output.return_value.invoke.return_value = ReferenceGrade(
        matches_reference=True,
        reason="Offline stub verdict.",
    )

    def choose_model(model, *arguments):
        if model == "candidate-test":
            return candidate
        if model == "judge-test":
            return judge
        raise AssertionError(f"Unexpected model: {model}")

    factory = Mock(side_effect=choose_model)
    monkeypatch.setattr("archivist.qa.get_chat_model", factory)
    return judge, factory


def test_unified_entry_saves_report_with_separate_models(monkeypatch, offline_models):
    _, factory = offline_models
    monkeypatch.setenv("ARCHIVIST_CHAT_MODEL", "previous-model")

    run_entry(monkeypatch)

    run_dir = next(Path("storage/eval-runs").iterdir())
    report = read_json(run_dir / "report.json")

    assert report["run_id"] == run_dir.name
    assert report["parameters"]["chat_model"] == "candidate-test"
    assert report["judge"]["model"] == "judge-test"
    assert report["metrics"]["cases"] == report["metrics"]["graded_cases"] == 2
    assert report["metrics"]["reference_matches"] == 2
    assert [call.args[0] for call in factory.call_args_list] == [
        "candidate-test",
        "judge-test",
    ]
    assert [call.args[3] for call in factory.call_args_list] == [0.2, 0.0]
    assert os.environ["ARCHIVIST_CHAT_MODEL"] == "previous-model"
    assert sys.argv == ENTRY_ARGS


def test_unified_entry_stops_and_restores_environment_on_judge_failure(
    monkeypatch, offline_models, capsys
):
    judge, _ = offline_models
    monkeypatch.delenv("ARCHIVIST_CHAT_MODEL", raising=False)
    judge.with_structured_output.return_value.invoke.side_effect = RuntimeError(
        "judge unavailable"
    )

    with pytest.raises(RuntimeError, match="judge unavailable"):
        run_entry(monkeypatch)

    run_dir = next(Path("storage/eval-runs").iterdir())
    metadata_path = next((run_dir / "reference-grades").glob("*/metadata.json"))
    metadata = read_json(metadata_path)

    assert read_json(run_dir / "manifest.json")["status"] == "completed"
    assert metadata["status"] == "incomplete"
    assert metadata["graded_cases"] == 0
    assert not (run_dir / "report.json").exists()
    assert "Running report_eval.py" not in capsys.readouterr().out
    assert "ARCHIVIST_CHAT_MODEL" not in os.environ
    assert sys.argv == ENTRY_ARGS
