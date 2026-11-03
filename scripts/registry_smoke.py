import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from archivist.metadata import build_file_metadata
from archivist.registry import get_record, initialize_registry, save_record

path = Path("data/hash_sample.txt")
metadata = build_file_metadata(path, ingested_at=datetime.now(UTC))

registry_path = Path("storage/registry-smoke.sqlite3")
registry_path.parent.mkdir(parents=True, exist_ok=True)

with closing(sqlite3.connect(registry_path)) as connection:
    initialize_registry(connection)
    previous = get_record(connection, metadata.source)
    save_record(connection, metadata)
    saved = get_record(connection, metadata.source)

print(f"Previous record: {previous}")
print(f"Saved record: {saved}")

assert saved == metadata
print("Registry round-trip check passed.")
