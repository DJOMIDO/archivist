import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archivist.index_profile import IndexProfile
from archivist.pipeline import ensure_query_compatible
from archivist.registry import ensure_index_profile, initialize_registry

parser = argparse.ArgumentParser()
parser.add_argument("--embedding-model", default="offline-test-embedding")
parser.add_argument("--embedding-base-url", default="http://localhost:1234/v1")
parser.add_argument("--without-profile", action="store_true")
args = parser.parse_args()

profile = IndexProfile(
    embedding_model="offline-test-embedding",
    embedding_base_url="http://localhost:1234/v1",
    chunk_size=1000,
    chunk_overlap=200,
    separators=[" "],
    python="3.13.5",
    packages={},
)

with TemporaryDirectory() as directory:
    registry_path = Path(directory) / "registry.sqlite3"
    with closing(sqlite3.connect(registry_path)) as registry:
        initialize_registry(registry)
        if not args.without_profile:
            ensure_index_profile(registry, profile)

        registry_uri = registry_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(registry_uri, uri=True)) as registry:
        ensure_query_compatible(
            registry,
            embedding_model=args.embedding_model,
            embedding_base_url=args.embedding_base_url,
        )

    print("Query embedding configuration matches.")
