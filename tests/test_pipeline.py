from pathlib import Path

import pytest
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel

from archivist import pipeline


@pytest.fixture
def store(tmp_path: Path) -> Chroma:
    return Chroma(
        embedding_function=DeterministicFakeEmbedding(size=16),
        persist_directory=str(tmp_path / "chroma"),
    )


@pytest.fixture
def notes(tmp_path: Path) -> Path:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "redis.md").write_text("Redis is an in-memory database.", encoding="utf-8")
    (notes / "git.md").write_text("git rebase rewrites history.", encoding="utf-8")
    return notes


def test_ingest_reports_documents_and_chunks(notes: Path, store: Chroma):
    result = pipeline.ingest(notes, store, chunk_size=1000, chunk_overlap=100)

    assert result == pipeline.IngestResult(documents=2, chunks=2)
    assert len(store.get()["ids"]) == 2


def test_ask_answers_from_ingested_documents(notes: Path, store: Chroma):
    pipeline.ingest(notes, store, chunk_size=1000, chunk_overlap=100)
    llm = FakeListChatModel(responses=["It keeps data in memory [1]."])

    answer = pipeline.ask("Redis is an in-memory database.", store, llm, k=1)

    assert answer.text == "It keeps data in memory [1]."
    assert answer.sources == [str((notes / "redis.md").resolve())]
