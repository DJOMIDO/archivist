from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from langchain_core.documents import Document

from archivist.metadata import (
    FileMetadata,
    attach_file_metadata,
    build_file_metadata,
    hash_file,
)
from archivist.splitting import split_documents


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            b"",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
        (
            b"abc",
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        ),
    ],
)
def test_hash_file_matches_known_sha256(tmp_path: Path, content: bytes, expected: str):
    path = tmp_path / "sample.bin"
    path.write_bytes(content)

    assert hash_file(path) == expected


def test_hash_file_detects_changes_and_restoration(tmp_path: Path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"original")
    original_hash = hash_file(path)

    assert hash_file(path) == original_hash

    path.write_bytes(b"changed")
    assert hash_file(path) != original_hash

    path.write_bytes(b"original")
    assert hash_file(path) == original_hash


def test_hash_file_is_independent_of_path(tmp_path: Path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_bytes(b"same content")
    second.write_bytes(b"same content")

    assert hash_file(first) == hash_file(second)


def test_hash_file_preserves_binary_and_newline_differences(tmp_path: Path):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"\xff\x00\r\n")
    second.write_bytes(b"\xff\x00\n")

    assert hash_file(first) != hash_file(second)


def test_hash_file_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        hash_file(tmp_path / "missing.txt")


@pytest.mark.parametrize(
    "ingested_at",
    [
        datetime(2026, 11, 3, 12, tzinfo=UTC),
        datetime(
            2026,
            11,
            3,
            13,
            tzinfo=timezone(timedelta(hours=1)),
        ),
    ],
)
def test_build_file_metadata_normalizes_time_and_maps_fields(
    tmp_path: Path, ingested_at: datetime
):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"abc")

    metadata = build_file_metadata(path, ingested_at=ingested_at)

    assert metadata == FileMetadata(
        source=str(path.resolve()),
        content_hash=(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        ),
        ingested_at="2026-11-03T12:00:00+00:00",
    )


def test_build_file_metadata_rejects_time_without_timezone(tmp_path: Path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"abc")

    with pytest.raises(ValueError, match="timezone"):
        build_file_metadata(
            path,
            ingested_at=datetime(2026, 11, 3, 12),
        )


def test_build_file_metadata_keeps_hash_independent_of_time(tmp_path: Path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"abc")
    first_time = datetime(2026, 11, 3, 12, tzinfo=UTC)

    first = build_file_metadata(path, ingested_at=first_time)
    second = build_file_metadata(
        path,
        ingested_at=first_time + timedelta(hours=1),
    )

    assert first.source == second.source
    assert first.content_hash == second.content_hash
    assert first.ingested_at == "2026-11-03T12:00:00+00:00"
    assert second.ingested_at == "2026-11-03T13:00:00+00:00"


@pytest.fixture
def file_metadata() -> FileMetadata:
    return FileMetadata(
        source="/notes/source",
        content_hash="a" * 64,
        ingested_at="2026-11-03T12:00:00+00:00",
    )


@pytest.mark.parametrize(
    "location",
    [
        {"file_type": "pdf", "page": 2},
        {"file_type": "epub", "section": "a.xhtml"},
    ],
)
def test_attach_file_metadata_preserves_fields_through_splitting(
    file_metadata: FileMetadata, location: dict[str, str | int]
):
    original_metadata = {"source": file_metadata.source, **location}
    original = Document(
        id="original-id",
        page_content="Alpha beta gamma delta.",
        metadata=original_metadata,
    )

    documents = attach_file_metadata([original], file_metadata)

    assert len(documents) == 1
    enriched = documents[0]
    assert enriched is not original
    assert enriched.id == "original-id"
    assert enriched.page_content == original.page_content
    assert original.metadata == original_metadata

    expected = {
        "source": file_metadata.source,
        "content_hash": file_metadata.content_hash,
        "ingested_at": file_metadata.ingested_at,
        **location,
    }
    assert enriched.metadata == expected

    chunks = split_documents(documents, chunk_size=10, chunk_overlap=2)

    assert len(chunks) > 1
    for chunk in chunks:
        assert "start_index" in chunk.metadata
        assert all(chunk.metadata[key] == value for key, value in expected.items())


def test_attach_file_metadata_creates_independent_dictionaries(
    file_metadata: FileMetadata,
):
    original = Document(
        page_content="Alpha",
        metadata={"source": file_metadata.source, "page": 1},
    )

    documents = attach_file_metadata([original, original], file_metadata)
    documents[0].metadata["page"] = 99

    assert documents[1].metadata["page"] == 1
    assert original.metadata == {
        "source": file_metadata.source,
        "page": 1,
    }


@pytest.mark.parametrize("source", ["/notes/other", None])
def test_attach_file_metadata_rejects_wrong_or_missing_source(
    file_metadata: FileMetadata, source: str | None
):
    original = Document(
        page_content="Alpha",
        metadata={} if source is None else {"source": source},
    )

    with pytest.raises(ValueError, match="source"):
        attach_file_metadata([original], file_metadata)
