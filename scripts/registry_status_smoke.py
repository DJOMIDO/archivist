import sqlite3
from contextlib import closing
from pathlib import Path

from archivist.metadata import hash_file
from archivist.registry import get_content_status

path = Path("data/hash_sample.txt")
source = str(path.resolve())
current_hash = hash_file(path)

registry_path = Path("storage/registry-smoke.sqlite3")
registry_uri = registry_path.resolve().as_uri() + "?mode=ro"

with closing(sqlite3.connect(registry_uri, uri=True)) as connection:
    status = get_content_status(connection, source, current_hash)

print(f"Source: {source}")
print(f"Current hash: {current_hash}")
print(f"Content status: {status}")
