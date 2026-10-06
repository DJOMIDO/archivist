from langchain_core.documents import Document

from archivist.splitting import split_documents


def make_doc(text: str) -> Document:
    return Document(page_content=text, metadata={"source": "/notes/a.md"})


def test_chunks_respect_size_and_keep_metadata():
    doc = make_doc("word" * 200)

    chunks = split_documents([doc], chunk_size=100, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(len(c.page_content) <= 100 for c in chunks)
    assert all(c.metadata["source"] == "/notes/a.md" for c in chunks)


def test_start_index_points_back_into_original_text():
    doc = make_doc("alpha beta gamma delta. " * 30)

    chunks = split_documents([doc], chunk_size=80, chunk_overlap=0)

    for chunk in chunks:
        start = chunk.metadata["start_index"]
        assert doc.page_content[start : start + len(chunk.page_content)] == (
            chunk.page_content
        )


def test_chinese_text_splits_at_sentence_end():
    doc = make_doc("这是一个用来测试切分的句子。" * 20)

    chunks = split_documents([doc], chunk_size=50, chunk_overlap=0)

    assert len(chunks) > 1
    assert all(c.page_content.endswith("。") for c in chunks)


def test_short_document_stays_whole():
    doc = make_doc("short note")

    chunks = split_documents([doc], chunk_size=100, chunk_overlap=10)

    assert [c.page_content for c in chunks] == ["short note"]
