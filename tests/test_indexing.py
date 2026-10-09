from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from pydantic import SecretStr

from archivist.indexing import chunk_id, get_embeddings, get_vector_store, index_chunks


def make_chunk(text: str, start: int) -> Document:
    return Document(
        page_content=text, metadata={"source": "/notes/a.md", "start_index": start}
    )


def test_chunk_id_is_stable():
    assert chunk_id(make_chunk("x", 42)) == "/notes/a.md:42"


def test_index_chunks_persists_to_disk(tmp_path: Path):
    embeddings = DeterministicFakeEmbedding(size=16)
    store = get_vector_store(embeddings, tmp_path)

    index_chunks(store, [make_chunk("hello", 0), make_chunk("world", 5)])

    reopened = get_vector_store(embeddings, tmp_path)
    assert len(reopened.get()["ids"]) == 2


def test_reindexing_does_not_duplicate(tmp_path: Path):
    store = get_vector_store(DeterministicFakeEmbedding(size=16), tmp_path)
    chunks = [make_chunk("hello", 0), make_chunk("word", 5)]

    index_chunks(store, chunks)
    index_chunks(store, chunks)

    assert len(store.get()["ids"]) == 2


def test_index_empty_list_is_noop(tmp_path: Path):
    store = get_vector_store(DeterministicFakeEmbedding(size=16), tmp_path)

    assert index_chunks(store, []) == 0


def test_embeddings_factory_sends_raw_text():
    embeddings = get_embeddings(
        "some-model", "http://localhost:1234/v1", SecretStr("x")
    )

    assert embeddings.check_embedding_ctx_length is False
