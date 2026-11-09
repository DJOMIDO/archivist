import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archivist.chunk_manifest import build_chunk_manifest
from archivist.registry import (
    get_chunk_manifest,
    initialize_registry,
    save_chunk_manifest,
)

source = "/notes/example.md"
expected = build_chunk_manifest(["chunk-1", "chunk-2"], ["First chunk", "Second chunk"])

with TemporaryDirectory() as directory:
    path = Path(directory) / "registry.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        initialize_registry(connection)
        save_chunk_manifest(connection, source, expected)

    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        restored = get_chunk_manifest(connection, source)

    assert restored is not None
    assert restored == expected
    print(f"Restored chunks: {len(restored)}")
    print("Manifest round-trip check passed.")
