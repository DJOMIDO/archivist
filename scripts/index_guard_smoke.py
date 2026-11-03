import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from archivist.index_profile import IndexProfile
from archivist.indexing import get_vector_store
from archivist.pipeline import ensure_index_compatible
from archivist.registry import initialize_registry

parser = argparse.ArgumentParser()
parser.add_argument("--seed-existing-vector", action="store_true")
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

with (
    TemporaryDirectory() as directory,
    closing(sqlite3.connect(":memory:")) as registry,
):
    initialize_registry(registry)
    store = get_vector_store(
        DeterministicFakeEmbedding(size=16),
        Path(directory) / "chroma",
    )

    if args.seed_existing_vector:
        store.add_documents(
            [
                Document(
                    page_content="Legacy content",
                    metadata={"source": "/notes/legacy.md"},
                )
            ],
            ids=["legacy-chunk"],
        )

    created = ensure_index_compatible(store, registry, profile)
    print(f"Created profile: {created}")
