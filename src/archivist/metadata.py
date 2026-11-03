"""Build shared file metadata for document ingestion."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import file_digest
from pathlib import Path

from langchain_core.documents import Document


@dataclass(frozen=True)
class FileMetadata:
    """File-level metadata shared by all Documents from one ingestion."""

    source: str
    content_hash: str
    ingested_at: str


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's raw bytes."""
    with path.open("rb") as file:
        return file_digest(file, "sha256").hexdigest()


def build_file_metadata(path: Path, ingested_at: datetime) -> FileMetadata:
    """Build file metadata using an explicit timezone-aware ingestion time."""
    if ingested_at.utcoffset() is None:
        raise ValueError("ingested_at must include a timezone")

    return FileMetadata(
        source=str(path.resolve()),
        content_hash=hash_file(path),
        ingested_at=ingested_at.astimezone(UTC).isoformat(),
    )


def attach_file_metadata(
    documents: list[Document], metadata: FileMetadata
) -> list[Document]:
    """Copy Documents with shared metadata, requiring matching sources."""
    shared = asdict(metadata)
    enriched: list[Document] = []

    for document in documents:
        if document.metadata.get("source") != metadata.source:
            raise ValueError("Document source does not match file metadata")

        enriched.append(
            document.model_copy(update={"metadata": {**document.metadata, **shared}})
        )

    return enriched
