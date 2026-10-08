import pytest
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from typer.testing import CliRunner

from archivist.cli import app

runner = CliRunner()


def test_config_command_prints_settings():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "chat_model" in result.output


def test_config_command_reflects_env_override(monkeypatch):
    monkeypatch.setenv("ARCHIVIST_CHAT_MODEL", "my-test-model")
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "chat_model = my-test-model" in result.output


@pytest.fixture
def fake_backends(tmp_path, monkeypatch):
    """Replace Ollama-backed factories in the CLI with offline fakes."""
    store = Chroma(
        embedding_function=DeterministicFakeEmbedding(size=16),
        persist_directory=str(tmp_path / "chroma"),
    )
    llm = FakeListChatModel(responses=["Redis keeps data in memory [1]."])
    monkeypatch.setattr("archivist.cli.open_vector_store", lambda settings: store)
    monkeypatch.setattr("archivist.cli.get_chat_model", lambda *args: llm)
    return store


def test_ingest_then_ask(tmp_path, fake_backends):
    (tmp_path / "redis.md").write_text("Redis is in memory.", encoding="utf-8")

    ingested = runner.invoke(app, ["ingest", str(tmp_path / "redis.md")])
    asked = runner.invoke(app, ["ask", "Redis is in memory.", "--top-k", "1"])

    assert ingested.exit_code == 0
    assert "Ingested 1 documents (1 chunks)." in ingested.output
    assert asked.exit_code == 0
    assert "Redis keeps data in memory [1]." in asked.output
    assert "redis.md" in asked.output


def test_ingest_missing_path_fails(tmp_path, fake_backends):
    result = runner.invoke(app, ["ingest", str(tmp_path / "nope")])

    assert result.exit_code != 0
