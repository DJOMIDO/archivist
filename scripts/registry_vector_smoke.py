import sqlite3
from contextlib import closing
from tempfile import TemporaryDirectory

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from archivist.chunk_manifest import build_chunk_manifest
from archivist.metadata import FileMetadata
from archivist.registry import get_content_status, initialize_registry, save_record

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
    expected_ids = set(expected_hashes)

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

        result = store.get(where={"source": record.source}, include=["documents"])
        actual_hashes = build_chunk_manifest(result["ids"], result["documents"])
        actual_ids = set(actual_hashes)
        missing = expected_ids - actual_ids
        extra = actual_ids - expected_ids
        changed = {
            chunk_id
            for chunk_id in expected_ids & actual_ids
            if expected_hashes[chunk_id] != actual_hashes[chunk_id]
        }
        status = get_content_status(registry, record.source, record.content_hash)
        print(
            f"{stage}: content={status}, "
            f"ids_match={actual_ids == expected_ids}, "
            f"texts_match={actual_hashes == expected_hashes}"
        )
        print(
            f"  missing={sorted(missing)}, extra={sorted(extra)}, "
            f"changed={sorted(changed)}"
        )
