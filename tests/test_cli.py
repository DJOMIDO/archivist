import sqlite3
from contextlib import closing
from unittest.mock import Mock

import httpx
import pytest
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from openai import APIConnectionError
from typer.testing import CliRunner

from archivist.cli import app
from archivist.config import get_settings
from archivist.registry import get_index_profile, get_record

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
    """Replace model-server-backed factories in the CLI with offline fakes."""
    monkeypatch.setenv("ARCHIVIST_STORAGE_DIR", str(tmp_path / "storage"))
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

    with closing(
        sqlite3.connect(tmp_path / "storage" / "registry.sqlite3")
    ) as registry:
        profile = get_index_profile(registry)

    settings = get_settings()
    assert profile is not None
    assert profile.embedding_model == settings.embedding_model
    assert profile.embedding_base_url == settings.llm_base_url
    assert profile.chunk_size == settings.chunk_size
    assert profile.chunk_overlap == settings.chunk_overlap


def test_ingest_missing_path_fails(tmp_path, fake_backends):
    result = runner.invoke(app, ["ingest", str(tmp_path / "nope")])

    assert result.exit_code != 0


def test_unreachable_model_server_gives_short_error(monkeypatch, fake_backends):
    def refuse(*args, **kwargs):
        raise APIConnectionError(request=httpx.Request("POST", "http://localhost"))

    monkeypatch.setattr("archivist.cli.pipeline.ask", refuse)

    result = runner.invoke(app, ["ask", "anything"])

    assert result.exit_code == 1
    assert "cannot reach the model server" in result.output
    assert "Traceback" not in result.output


def test_ask_displays_pdf_page(fake_backends):
    fake_backends.add_documents(
        [
            Document(
                page_content="Redis is in memory.",
                metadata={"source": "/notes/lab.pdf", "page": 7},
            )
        ],
        ids=["pdf-page-7"],
    )

    result = runner.invoke(app, ["ask", "Redis is in memory.", "--top-k", "1"])

    assert result.exit_code == 0
    assert "Redis keeps data in memory [1]." in result.output
    assert "Sources:\n  - /notes/lab.pdf, page 7" in result.output


def test_ask_displays_epub_section(fake_backends):
    fake_backends.add_documents(
        [
            Document(
                page_content="Redis is in memory.",
                metadata={
                    "source": "/notes/book.epub",
                    "section": "b.xhtml",
                },
            )
        ],
        ids=["epub-section-b"],
    )

    result = runner.invoke(app, ["ask", "Redis is in memory.", "--top-k", "1"])

    assert result.exit_code == 0
    assert "Redis keeps data in memory [1]." in result.output
    assert "Sources:\n  - /notes/book.epub, section b.xhtml" in result.output


def test_ingest_rejects_unprofiled_vectors_before_ingestion(
    tmp_path, fake_backends, monkeypatch
):
    path = tmp_path / "note.md"
    path.write_text("New content", encoding="utf-8")
    fake_backends.add_documents(
        [Document(page_content="Old content", metadata={"source": "/old.md"})],
        ids=["old-chunk"],
    )
    before = fake_backends.get(include=["documents", "metadatas"])
    ingest = Mock(side_effect=AssertionError("ingest should not run"))
    monkeypatch.setattr("archivist.cli.pipeline.ingest", ingest)

    result = runner.invoke(app, ["ingest", str(path)])

    assert result.exit_code == 1
    assert "Error: Vectors exist without an index profile" in result.output
    ingest.assert_not_called()
    assert fake_backends.get(include=["documents", "metadatas"]) == before
    with closing(
        sqlite3.connect(tmp_path / "storage" / "registry.sqlite3")
    ) as registry:
        assert get_index_profile(registry) is None
        assert registry.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0


def test_ingest_rejects_profile_changes_before_ingestion(
    tmp_path, fake_backends, monkeypatch
):
    monkeypatch.setenv("ARCHIVIST_CHUNK_SIZE", "1000")
    monkeypatch.setenv("ARCHIVIST_CHUNK_OVERLAP", "200")
    path = tmp_path / "note.md"
    path.write_text("New content", encoding="utf-8")
    first = runner.invoke(app, ["ingest", str(path)])
    assert first.exit_code == 0, first.exception

    with closing(
        sqlite3.connect(tmp_path / "storage" / "registry.sqlite3")
    ) as registry:
        previous_profile = get_index_profile(registry)
        previous_record = get_record(registry, str(path.resolve()))
    before = fake_backends.get(include=["documents", "metadatas"])

    monkeypatch.setenv("ARCHIVIST_CHUNK_SIZE", "800")
    get_settings.cache_clear()
    ingest = Mock(side_effect=AssertionError("ingest should not run"))
    monkeypatch.setattr("archivist.cli.pipeline.ingest", ingest)

    result = runner.invoke(app, ["ingest", str(path)])

    assert result.exit_code == 1
    assert "Error: Index profile changed" in result.output
    ingest.assert_not_called()
    assert fake_backends.get(include=["documents", "metadatas"]) == before
    with closing(
        sqlite3.connect(tmp_path / "storage" / "registry.sqlite3")
    ) as registry:
        assert get_index_profile(registry) == previous_profile
        assert get_record(registry, str(path.resolve())) == previous_record
