"""Store file-level ingestion records in SQLite."""

import json
import sqlite3
from typing import Literal

from pydantic import TypeAdapter

from archivist.index_profile import IndexProfile, fingerprint_index_profile
from archivist.metadata import FileMetadata

_CHUNK_MANIFEST_ADAPTER = TypeAdapter(dict[str, str])


def initialize_registry(connection: sqlite3.Connection) -> None:
    """Create file-record and index-profile tables if absent."""
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                source TEXT PRIMARY KEY NOT NULL,
                content_hash TEXT NOT NULL,
                ingested_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS index_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                profile_json TEXT NOT NULL,
                fingerprint TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_manifests (
                source TEXT PRIMARY KEY NOT NULL,
                manifest_json TEXT NOT NULL
            )
            """
        )


def get_record(connection: sqlite3.Connection, source: str) -> FileMetadata | None:
    """Return the record for a canonical source path, or None."""
    row = connection.execute(
        """
        SELECT source, content_hash, ingested_at
        FROM documents
        WHERE source = ?
        """,
        (source,),
    ).fetchone()

    if row is None:
        return None

    return FileMetadata(
        source=row[0],
        content_hash=row[1],
        ingested_at=row[2],
    )


def save_record(connection: sqlite3.Connection, metadata: FileMetadata) -> None:
    """Insert or update a source record and commit the write."""
    with connection:
        connection.execute(
            """
            INSERT INTO documents (source, content_hash, ingested_at)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                content_hash = excluded.content_hash,
                ingested_at = excluded.ingested_at
            """,
            (
                metadata.source,
                metadata.content_hash,
                metadata.ingested_at,
            ),
        )


def get_content_status(
    connection: sqlite3.Connection,
    source: str,
    content_hash: str,
) -> Literal["new", "unchanged", "changed"]:
    """Compare file content with its source record without modifying it."""
    previous = get_record(connection, source)
    if previous is None:
        return "new"
    if previous.content_hash == content_hash:
        return "unchanged"
    return "changed"


def get_index_profile(connection: sqlite3.Connection) -> IndexProfile | None:
    """Read a profile and verify its JSON/fingerprint agreement."""
    row = connection.execute(
        "SELECT profile_json, fingerprint FROM index_profile WHERE id = 1"
    ).fetchone()
    if row is None:
        return None

    profile = IndexProfile.model_validate_json(row[0])
    if fingerprint_index_profile(profile) != row[1]:
        raise ValueError("Stored profile fingerprint does not match its JSON")
    return profile


def ensure_index_profile(connection: sqlite3.Connection, profile: IndexProfile) -> bool:
    """Initialize a profile or require a match; return True when created."""
    previous = get_index_profile(connection)
    if previous is not None:
        if fingerprint_index_profile(previous) != fingerprint_index_profile(profile):
            raise ValueError(
                "Index profile changed; use a separate index or rebuild it"
            )
        return False

    if connection.execute("SELECT 1 FROM documents LIMIT 1").fetchone() is not None:
        raise ValueError("Registry has documents but no index profile; rebuild it")

    with connection:
        connection.execute(
            """
            INSERT INTO index_profile (id, profile_json, fingerprint)
            VALUES (1, ?, ?)
            """,
            (profile.model_dump_json(), fingerprint_index_profile(profile)),
        )
    return True


def get_chunk_manifest(
    connection: sqlite3.Connection, source: str
) -> dict[str, str] | None:
    """Read a source's text manifest, preserving missing versus empty."""
    row = connection.execute(
        "SELECT manifest_json FROM chunk_manifests WHERE source = ?",
        (source,),
    ).fetchone()
    if row is None:
        return None
    return _CHUNK_MANIFEST_ADAPTER.validate_json(row[0], strict=True)


def save_chunk_manifest(
    connection: sqlite3.Connection, source: str, manifest: dict[str, str]
) -> None:
    """Insert or replace a source's text manifest and commit the write."""
    validated = _CHUNK_MANIFEST_ADAPTER.validate_python(manifest, strict=True)
    serialized = json.dumps(validated, sort_keys=True, ensure_ascii=False)
    with connection:
        connection.execute(
            """
            INSERT INTO chunk_manifests (source, manifest_json)
            VALUES (?, ?)
            ON CONFLICT(source) DO UPDATE SET
                manifest_json = excluded.manifest_json
            """,
            (source, serialized),
        )
