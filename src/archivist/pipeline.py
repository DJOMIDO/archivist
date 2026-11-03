"""Wire the RAG steps together; shared by the CLI and (later) the web UI."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from archivist.indexing import index_chunks
from archivist.loaders import find_files, load_file
from archivist.metadata import attach_file_metadata, build_file_metadata
from archivist.qa import Answer, answer_question
from archivist.retrieval import retrieve
from archivist.splitting import split_documents


@dataclass
class IngestResult:
    documents: int
    chunks: int


def ingest(
    path: Path,
    vector_store: VectorStore,
    chunk_size: int,
    chunk_overlap: int,
    *,
    ingested_at: datetime,
) -> IngestResult:
    """Load files with shared metadata, then split and index their Documents."""
    documents: list[Document] = []

    for file_path in find_files(path):
        metadata = build_file_metadata(file_path, ingested_at=ingested_at)
        loaded = load_file(file_path)
        documents.extend(attach_file_metadata(loaded, metadata))

    chunks = split_documents(documents, chunk_size, chunk_overlap)
    index_chunks(vector_store, chunks)
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
