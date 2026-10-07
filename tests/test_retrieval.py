from pathlib import Path

import pytest
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from archivist.retrieval import retrieve


@pytest.fixture
def store(tmp_path: Path) -> Chroma:
    store = Chroma(
        embedding_function=DeterministicFakeEmbedding(size=16),
        persist_directory=str(tmp_path),
    )
    store.add_documents(
        [
            Document(page_content=text, metadata={"source": f"{text}.md"})
            for text in ("alpha", "beta", "gamma")
        ]
    )
    return store


def test_returns_at_most_k_results_closest_first(store: Chroma):
    results = retrieve(store, "beta", k=2)

    assert len(results) == 2
    distances = [distance for _, distance in results]
    assert distances == sorted(distances)


def test_exact_match_is_the_closest_result(store: Chroma):
    doc, distance = retrieve(store, "beta", k=3)[0]

    assert doc.page_content == "beta"
    assert distance == pytest.approx(0.0, abs=1e-6)


def test_max_distance_drops_far_results(store: Chroma):
    results = retrieve(store, "beta", k=3, max_distance=1e-6)

    assert [doc.page_content for doc, _ in results] == ["beta"]
