import sqlite3
from contextlib import closing
from tempfile import TemporaryDirectory

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from archivist.chunk_manifest import build_chunk_manifest
from archivist.metadata import FileMetadata
from archivist.pipeline import source_manifest_matches
from archivist.registry import (
    get_content_status,
    initialize_registry,
    save_chunk_manifest,
    save_record,
)

record = FileMetadata(
    source="/notes/example.md",
    content_hash="a" * 64,
    ingested_at="2026-11-04T12:00:00+00:00",
)

with (
    TemporaryDirectory() as directory,
    closing(sqlite3.connect(":memory:")) as registry,
):
    initialize_registry(registry)
    save_record(registry, record)
    store = Chroma(
        embedding_function=DeterministicFakeEmbedding(size=16),
        persist_directory=directory,
    )
    store.add_documents(
        [
            Document(page_content=text, metadata={"source": record.source})
            for text in ("First chunk", "Second chunk")
        ],
        ids=["chunk-1", "chunk-2"],
    )

    expected_hashes = build_chunk_manifest(
        ["chunk-1", "chunk-2"],
        ["First chunk", "Second chunk"],
    )
    save_chunk_manifest(registry, record.source, expected_hashes)

    for stage in ("complete", "tampered", "missing", "wrong_id"):
        if stage == "tampered":
            store.add_documents(
                [
                    Document(
                        page_content="Replaced text",
                        metadata={"source": record.source},
                    )
                ],
                ids=["chunk-2"],
            )
        elif stage == "missing":
            store.delete(ids=["chunk-2"])
        elif stage == "wrong_id":
            store.add_documents(
                [
                    Document(
                        page_content="Unexpected chunk",
                        metadata={"source": record.source},
                    )
                ],
                ids=["unexpected-chunk"],
            )

        status = get_content_status(registry, record.source, record.content_hash)
        matches = source_manifest_matches(store, registry, record.source)
        print(f"{stage}: content={status}, manifest_match={matches}")
