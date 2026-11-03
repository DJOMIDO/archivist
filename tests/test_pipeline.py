from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel

from archivist import pipeline
from archivist.metadata import hash_file


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
    result = pipeline.ingest(
        notes,
        store,
        chunk_size=1000,
        chunk_overlap=100,
        ingested_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
    )
    assert result == pipeline.IngestResult(documents=2, chunks=2)
    assert len(store.get()["ids"]) == 2


def test_ask_answers_from_ingested_documents(notes: Path, store: Chroma):
    pipeline.ingest(
        notes,
        store,
        chunk_size=1000,
        chunk_overlap=100,
        ingested_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
    )
    llm = FakeListChatModel(responses=["It keeps data in memory [1]."])

    answer = pipeline.ask("Redis is an in-memory database.", store, llm, k=1)

    assert answer.text == "It keeps data in memory [1]."
    assert answer.sources == [str((notes / "redis.md").resolve())]


def test_ingest_persists_file_metadata(notes: Path, store: Chroma, tmp_path: Path):
    result = pipeline.ingest(
        notes,
        store,
        chunk_size=12,
        chunk_overlap=2,
        ingested_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
    )

    reopened = Chroma(
        embedding_function=DeterministicFakeEmbedding(size=16),
        persist_directory=str(tmp_path / "chroma"),
    )
    records = reopened.get(include=["documents", "metadatas"])

    assert result.documents == 2
    assert len(records["ids"]) == result.chunks > 2

    expected_hashes = {str(path.resolve()): hash_file(path) for path in notes.iterdir()}
    assert {metadata["source"] for metadata in records["metadatas"]} == set(
        expected_hashes
    )

    for text, metadata in zip(records["documents"], records["metadatas"], strict=True):
        source = metadata["source"]
        assert metadata["content_hash"] == expected_hashes[source]
        assert metadata["ingested_at"] == "2026-11-03T12:00:00+00:00"
        assert metadata["file_type"] == "md"

        start = metadata["start_index"]
        assert isinstance(start, int)
        assert start >= 0

        original = Path(source).read_text(encoding="utf-8")
        assert text == original[start : start + len(text)]
