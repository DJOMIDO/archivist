import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from archivist.index_profile import IndexProfile, fingerprint_index_profile
from archivist.metadata import FileMetadata
from archivist.registry import (
    ensure_index_profile,
    get_chunk_manifest,
    get_content_status,
    get_index_profile,
    get_record,
    initialize_registry,
    save_chunk_manifest,
    save_record,
)


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(":memory:")) as connection:
        initialize_registry(connection)
        yield connection


@pytest.fixture
def record() -> FileMetadata:
    return FileMetadata(
        source="/notes/owner's guide.md",
        content_hash="a" * 64,
        ingested_at="2026-11-03T12:00:00+00:00",
    )


def test_get_record_returns_none_for_unknown_source(
    connection: sqlite3.Connection,
):
    assert get_record(connection, "/notes/missing.md") is None
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0


def test_registry_persists_after_reopening(tmp_path: Path, record: FileMetadata):
    path = tmp_path / "registry.sqlite3"

    with closing(sqlite3.connect(path)) as connection:
        initialize_registry(connection)
        save_record(connection, record)

    with closing(sqlite3.connect(path)) as connection:
        initialize_registry(connection)
        assert get_record(connection, record.source) == record


def test_save_record_updates_existing_source(
    connection: sqlite3.Connection, record: FileMetadata
):
    save_record(connection, record)
    updated = FileMetadata(
        source=record.source,
        content_hash="b" * 64,
        ingested_at="2026-11-03T13:00:00+00:00",
    )

    save_record(connection, updated)

    assert get_record(connection, record.source) == updated
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1


def test_registry_keeps_distinct_sources_with_same_hash(
    connection: sqlite3.Connection, record: FileMetadata
):
    second = FileMetadata(
        source="/notes/copy.md",
        content_hash=record.content_hash,
        ingested_at=record.ingested_at,
    )

    save_record(connection, record)
    save_record(connection, second)

    assert get_record(connection, record.source) == record
    assert get_record(connection, second.source) == second
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2


@pytest.mark.parametrize(
    ("previous_hash", "expected"),
    [
        (None, "new"),
        ("b" * 64, "unchanged"),
        ("a" * 64, "changed"),
    ],
)
def test_get_content_status_does_not_modify_records(
    connection: sqlite3.Connection,
    previous_hash: str | None,
    expected: str,
):
    source = "/notes/sample.md"
    previous = None
    if previous_hash is not None:
        previous = FileMetadata(
            source=source,
            content_hash=previous_hash,
            ingested_at="2026-11-03T12:00:00+00:00",
        )
        save_record(connection, previous)

    assert get_content_status(connection, source, "b" * 64) == expected
    assert get_record(connection, source) == previous

    count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert count == int(previous is not None)


@pytest.fixture
def profile() -> IndexProfile:
    return IndexProfile(
        embedding_model="test-embedding",
        embedding_base_url="http://localhost:1234/v1",
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "。", " ", ""],
        python="3.13.5",
        packages={"pypdf": "6.0.0"},
    )


def test_index_profile_persists_after_reopening(tmp_path: Path, profile: IndexProfile):
    path = tmp_path / "registry.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        initialize_registry(connection)
        assert get_index_profile(connection) is None
        assert ensure_index_profile(connection, profile) is True

    with closing(sqlite3.connect(path)) as connection:
        initialize_registry(connection)
        assert get_index_profile(connection) == profile
        assert ensure_index_profile(connection, profile) is False
        assert (
            connection.execute("SELECT COUNT(*) FROM index_profile").fetchone()[0] == 1
        )


def test_index_profile_mismatch_preserves_baseline(
    connection: sqlite3.Connection, profile: IndexProfile
):
    ensure_index_profile(connection, profile)
    changed = IndexProfile.model_validate({**profile.model_dump(), "chunk_size": 800})

    with pytest.raises(ValueError, match="Index profile changed"):
        ensure_index_profile(connection, changed)

    assert get_index_profile(connection) == profile


@pytest.mark.parametrize(
    "damage",
    ["invalid_json", "invalid_profile", "changed_json", "changed_hash"],
)
def test_index_profile_rejects_corruption_without_overwriting(
    connection: sqlite3.Connection, profile: IndexProfile, damage: str
):
    ensure_index_profile(connection, profile)
    serialized = profile.model_dump_json()
    fingerprint = fingerprint_index_profile(profile)

    if damage == "invalid_json":
        serialized = "{"
    elif damage == "invalid_profile":
        serialized = "{}"
    elif damage == "changed_json":
        changed = IndexProfile.model_validate(
            {**profile.model_dump(), "chunk_size": 800}
        )
        serialized = changed.model_dump_json()
    else:
        fingerprint = "0" * 64

    with connection:
        connection.execute(
            "UPDATE index_profile SET profile_json = ?, fingerprint = ? WHERE id = 1",
            (serialized, fingerprint),
        )

    with pytest.raises(ValueError):
        ensure_index_profile(connection, profile)

    assert connection.execute(
        "SELECT profile_json, fingerprint FROM index_profile WHERE id = 1"
    ).fetchone() == (serialized, fingerprint)


def test_index_profile_cannot_relabel_existing_file_records(
    connection: sqlite3.Connection,
    profile: IndexProfile,
    record: FileMetadata,
):
    save_record(connection, record)

    with pytest.raises(ValueError, match="Registry has documents"):
        ensure_index_profile(connection, profile)

    assert get_index_profile(connection) is None
    assert get_record(connection, record.source) == record


def test_chunk_manifest_persists_after_reopening(tmp_path: Path):
    path = tmp_path / "registry.sqlite3"
    source = "/notes/owner's guide.md"
    expected = {"chunk-1": "a" * 64, "chunk-2": "b" * 64}
    with closing(sqlite3.connect(path)) as connection:
        initialize_registry(connection)
        save_chunk_manifest(connection, source, expected)

    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        assert get_chunk_manifest(connection, source) == expected
        assert connection.total_changes == 0


def test_chunk_manifest_distinguishes_missing_and_empty(connection):
    assert get_chunk_manifest(connection, "/notes/empty.md") is None

    save_chunk_manifest(connection, "/notes/empty.md", {})

    assert get_chunk_manifest(connection, "/notes/empty.md") == {}
    assert get_chunk_manifest(connection, "/notes/unknown.md") is None


@pytest.mark.parametrize("replacement", [{"new-chunk": "c" * 64}, {}])
def test_chunk_manifest_replacement_preserves_other_sources(connection, replacement):
    source = "/notes/first.md"
    other = "/notes/second.md"
    save_chunk_manifest(connection, source, {"old-chunk": "a" * 64})
    save_chunk_manifest(connection, other, {"other-chunk": "b" * 64})

    save_chunk_manifest(connection, source, replacement)

    assert get_chunk_manifest(connection, source) == replacement
    assert get_chunk_manifest(connection, other) == {"other-chunk": "b" * 64}
    assert connection.execute("SELECT COUNT(*) FROM chunk_manifests").fetchone()[0] == 2


@pytest.mark.parametrize("invalid", [[], {"chunk-1": 123}, {123: "a" * 64}])
def test_invalid_chunk_manifest_save_preserves_registry(connection, invalid):
    source = "/notes/first.md"
    save_chunk_manifest(connection, source, {"old-chunk": "a" * 64})
    before = tuple(connection.iterdump())

    with pytest.raises(ValueError):
        save_chunk_manifest(connection, source, invalid)

    assert tuple(connection.iterdump()) == before


@pytest.mark.parametrize("serialized", ["not json", "[]", "null", '{"chunk-1": 123}'])
def test_chunk_manifest_read_rejects_corrupt_data(connection, serialized):
    source = "/notes/corrupt.md"
    with connection:
        connection.execute(
            "INSERT INTO chunk_manifests (source, manifest_json) VALUES (?, ?)",
            (source, serialized),
        )
    before = tuple(connection.iterdump())

    with pytest.raises(ValueError):
        get_chunk_manifest(connection, source)

    assert tuple(connection.iterdump()) == before
