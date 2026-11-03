import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from archivist.metadata import build_file_metadata

path = Path("data/hash_sample.txt")
metadata = build_file_metadata(path, ingested_at=datetime.now(UTC))

registry_path = Path("storage/registry-smoke.sqlite3")
registry_path.parent.mkdir(parents=True, exist_ok=True)

connection = sqlite3.connect(registry_path)
try:
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
        previous = connection.execute(
            "SELECT content_hash FROM documents WHERE source = ?",
            (metadata.source,),
        ).fetchone()

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
        count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
finally:
    connection.close()

print(f"Previous hash: {previous}")
print(f"Current hash: {metadata.content_hash}")
print(f"Rows: {count}")
