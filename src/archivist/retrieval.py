"""Find the chunks most relevant to a question."""

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore


def retrieve(
    vector_store: VectorStore,
    query: str,
    k: int,
    max_distance: float | None = None,
) -> list[tuple[Document, float]]:
    """Return up to `k` (chunk, distance) pairs, closest first.

    Lower distance means more similar. If `max_distance` is set, chunks farther
    away than it are dropped, so an off-topic question can return nothing.
    """
    results = vector_store.similarity_search_with_score(query, k=k)
    if max_distance is None:
        return results
    return [(doc, distance) for doc, distance in results if distance <= max_distance]
