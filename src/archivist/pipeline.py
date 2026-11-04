"""Wire the RAG steps together; shared by the CLI and (later) the web UI."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from archivist.index_profile import IndexProfile
from archivist.indexing import index_chunks
from archivist.loaders import find_files, load_file
from archivist.metadata import (
    FileMetadata,
    attach_file_metadata,
    build_file_metadata,
)
from archivist.qa import Answer, answer_question
from archivist.registry import (
    ensure_index_profile,
    get_index_profile,
    save_record,
)
from archivist.retrieval import retrieve
from archivist.splitting import split_documents


@dataclass
class IngestResult:
    documents: int
    chunks: int


def ensure_index_compatible(
    vector_store: Chroma,
    registry: sqlite3.Connection,
    profile: IndexProfile,
) -> bool:
    """Check profile compatibility; return True if a new profile is created."""
    previous = get_index_profile(registry)
    if previous is None and vector_store.get(limit=1, include=[])["ids"]:
        raise ValueError(
            "Vectors exist without an index profile; use a separate index or rebuild it"
        )
    return ensure_index_profile(registry, profile)


def ensure_query_compatible(
    registry: sqlite3.Connection,
    *,
    embedding_model: str,
    embedding_base_url: str,
) -> IndexProfile:
    """Return the stored profile if requested embedding settings match."""
    stored = get_index_profile(registry)
    if stored is None:
        raise ValueError(
            "Index profile is missing; query compatibility cannot be verified"
        )

    requested = (embedding_model, embedding_base_url)
    recorded = (stored.embedding_model, stored.embedding_base_url)
    if requested != recorded:
        raise ValueError("Query embedding configuration does not match the index")

    return stored


def ingest(
    path: Path,
    vector_store: VectorStore,
    chunk_size: int,
    chunk_overlap: int,
    *,
    ingested_at: datetime,
    registry: sqlite3.Connection,
) -> IngestResult:
    """Index Documents, then save their file-level registry records."""
    documents: list[Document] = []
    records: list[FileMetadata] = []

    for file_path in find_files(path):
        metadata = build_file_metadata(file_path, ingested_at=ingested_at)
        loaded = load_file(file_path)
        documents.extend(attach_file_metadata(loaded, metadata))
        records.append(metadata)

    chunks = split_documents(documents, chunk_size, chunk_overlap)
    index_chunks(vector_store, chunks)

    for record in records:
        save_record(registry, record)

    return IngestResult(documents=len(documents), chunks=len(chunks))


def ask(
    question: str,
    vector_store: VectorStore,
    llm: BaseChatModel,
    k: int,
    max_distance: float | None = None,
) -> Answer:
    """Retrieve relevant chunks and answer the question from them."""
    results = retrieve(vector_store, question, k=k, max_distance=max_distance)
    return answer_question(question, [doc for doc, _ in results], llm)
