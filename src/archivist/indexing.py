"""Embed chunks and store them in a persistent Chroma vector store."""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings

COLLECTION_NAME = "archivist"


def get_embeddings(model: str, base_url: str) -> Embeddings:
    """Create the embedding model client (Ollama)."""
    return OllamaEmbeddings(model=model, base_url=base_url)


def get_vector_store(embeddings: Embeddings, persist_dir: Path) -> Chroma:
    """Open (or create) the persistent Chroma collection."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )


def chunk_id(chunk: Document) -> str:
    """Stable ID for a chunk: the same file position always maps to the same ID."""
    return f"{chunk.metadata['source']}:{chunk.metadata['start_index']}"


def index_chunks(vector_store: Chroma, chunks: list[Document]) -> int:
    """Embed and upsert chunks; re-indexing the same chunks does not duplicate them."""
    if not chunks:
        return 0
    vector_store.add_documents(chunks, ids=[chunk_id(c) for c in chunks])
    return len(chunks)
