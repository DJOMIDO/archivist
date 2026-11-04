import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel

from archivist import pipeline
from archivist.index_profile import IndexProfile
from archivist.metadata import build_file_metadata, hash_file
from archivist.registry import (
    ensure_index_profile,
    get_index_profile,
    get_record,
    initialize_registry,
    save_record,
)


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


def test_ingest_reports_documents_and_chunks(
    notes: Path, store: Chroma, registry: sqlite3.Connection
):
    result = pipeline.ingest(
        notes,
        store,
        chunk_size=1000,
        chunk_overlap=100,
        ingested_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
        registry=registry,
    )
    assert result == pipeline.IngestResult(documents=2, chunks=2)
    assert len(store.get()["ids"]) == 2


def test_ask_answers_from_ingested_documents(
    notes: Path, store: Chroma, registry: sqlite3.Connection
):
    pipeline.ingest(
        notes,
        store,
        chunk_size=1000,
        chunk_overlap=100,
        ingested_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
        registry=registry,
    )
    llm = FakeListChatModel(responses=["It keeps data in memory [1]."])

    answer = pipeline.ask("Redis is an in-memory database.", store, llm, k=1)

    assert answer.text == "It keeps data in memory [1]."
    assert answer.sources == [str((notes / "redis.md").resolve())]


def test_ingest_persists_file_metadata(
    notes: Path, store: Chroma, tmp_path: Path, registry: sqlite3.Connection
):
    result = pipeline.ingest(
        notes,
        store,
        chunk_size=12,
        chunk_overlap=2,
        ingested_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
        registry=registry,
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


@pytest.fixture
def registry(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(tmp_path / "registry.sqlite3")) as connection:
        initialize_registry(connection)
        yield connection


def test_ingest_persists_registry_records(
    notes: Path,
    store: Chroma,
    registry: sqlite3.Connection,
    tmp_path: Path,
):
    ingested_at = datetime(2026, 11, 3, 12, tzinfo=UTC)
    result = pipeline.ingest(
        notes,
        store,
        chunk_size=1000,
        chunk_overlap=100,
        ingested_at=ingested_at,
        registry=registry,
    )

    assert len(store.get()["ids"]) == result.chunks == 2
    with closing(sqlite3.connect(tmp_path / "registry.sqlite3")) as reopened:
        for path in notes.iterdir():
            expected = build_file_metadata(path, ingested_at=ingested_at)
            assert get_record(reopened, expected.source) == expected
        assert reopened.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2


@pytest.mark.parametrize("has_previous_record", [False, True])
def test_ingest_indexing_failure_preserves_registry(
    notes: Path,
    store: Chroma,
    registry: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    has_previous_record: bool,
):
    path = notes / "redis.md"
    source = str(path.resolve())
    previous = None
    if has_previous_record:
        previous = build_file_metadata(
            path, ingested_at=datetime(2026, 11, 3, 11, tzinfo=UTC)
        )
        save_record(registry, previous)
        path.write_text("Changed Redis content.", encoding="utf-8")

    def fail_indexing(vector_store, chunks):
        raise RuntimeError("simulated indexing failure")

    monkeypatch.setattr(pipeline, "index_chunks", fail_indexing)

    with pytest.raises(RuntimeError, match="simulated indexing failure"):
        pipeline.ingest(
            notes,
            store,
            chunk_size=1000,
            chunk_overlap=100,
            ingested_at=datetime(2026, 11, 3, 12, tzinfo=UTC),
            registry=registry,
        )

    assert get_record(registry, source) == previous
    assert get_record(registry, str((notes / "git.md").resolve())) is None


@pytest.fixture
def profile() -> IndexProfile:
    return IndexProfile(
        embedding_model="test-embedding",
        embedding_base_url="http://localhost:1234/v1",
        chunk_size=1000,
        chunk_overlap=200,
        separators=[" "],
        python="3.13.5",
        packages={},
    )


@pytest.fixture
def populated_store(store: Chroma) -> Chroma:
    store.add_documents(
        [
            Document(
                page_content="Existing content",
                metadata={"source": "/notes/existing.md"},
            )
        ],
        ids=["existing-chunk"],
    )
    return store


def test_ensure_index_compatible_initializes_empty_index(
    store: Chroma, registry: sqlite3.Connection, profile: IndexProfile
):
    assert pipeline.ensure_index_compatible(store, registry, profile) is True
    assert get_index_profile(registry) == profile
    assert store.get(limit=1, include=[])["ids"] == []


def test_ensure_index_compatible_rejects_unprofiled_vectors(
    populated_store: Chroma,
    registry: sqlite3.Connection,
    profile: IndexProfile,
):
    before = populated_store.get(include=["documents", "metadatas"])

    with pytest.raises(ValueError, match="Vectors exist without an index profile"):
        pipeline.ensure_index_compatible(populated_store, registry, profile)

    assert get_index_profile(registry) is None
    assert populated_store.get(include=["documents", "metadatas"]) == before


@pytest.mark.parametrize("profile_changed", [False, True])
def test_existing_index_requires_matching_profile(
    populated_store: Chroma,
    registry: sqlite3.Connection,
    profile: IndexProfile,
    profile_changed: bool,
):
    ensure_index_profile(registry, profile)
    current = (
        IndexProfile.model_validate({**profile.model_dump(), "chunk_size": 800})
        if profile_changed
        else profile
    )
    before = populated_store.get(include=["documents", "metadatas"])

    if profile_changed:
        with pytest.raises(ValueError, match="Index profile changed"):
            pipeline.ensure_index_compatible(populated_store, registry, current)
    else:
        assert (
            pipeline.ensure_index_compatible(populated_store, registry, current)
            is False
        )

    assert get_index_profile(registry) == profile
    assert populated_store.get(include=["documents", "metadatas"]) == before


@pytest.mark.parametrize(
    ("scenario", "expected_error"),
    [
        ("matching", None),
        ("model_changed", "Query embedding configuration does not match the index"),
        ("endpoint_changed", "Query embedding configuration does not match the index"),
        ("missing_profile", "Index profile is missing"),
    ],
)
def test_query_compatibility_is_read_only(
    registry: sqlite3.Connection,
    profile: IndexProfile,
    tmp_path: Path,
    scenario: str,
    expected_error: str | None,
):
    if scenario != "missing_profile":
        ensure_index_profile(registry, profile)

    before = tuple(registry.iterdump())
    embedding_model = (
        "other-embedding" if scenario == "model_changed" else profile.embedding_model
    )
    embedding_base_url = (
        "http://localhost:9999/v1"
        if scenario == "endpoint_changed"
        else profile.embedding_base_url
    )

    registry_uri = (tmp_path / "registry.sqlite3").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(registry_uri, uri=True)) as readonly:
        if expected_error is None:
            restored = pipeline.ensure_query_compatible(
                readonly,
                embedding_model=embedding_model,
                embedding_base_url=embedding_base_url,
            )
            assert restored == profile
        else:
            with pytest.raises(ValueError, match=expected_error):
                pipeline.ensure_query_compatible(
                    readonly,
                    embedding_model=embedding_model,
                    embedding_base_url=embedding_base_url,
                )

        assert readonly.total_changes == 0

    assert tuple(registry.iterdump()) == before
