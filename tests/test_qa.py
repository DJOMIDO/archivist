from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel
from pydantic import SecretStr

from archivist.qa import (
    Citation,
    answer_question,
    cited_references,
    cited_sources,
    format_context,
    get_chat_model,
    not_found_message,
)


def make_chunk(text: str, source: str) -> Document:
    return Document(page_content=text, metadata={"source": source})


CHUNKS = [
    make_chunk("Docker images are read-only templates.", "/notes/docker.md"),
    make_chunk("Redis is an in-memory database.", "/notes/redis.md"),
    make_chunk("Containers are running images.", "/notes/docker.md"),
]


def test_format_context_numbers_chunks_and_shows_file_name():
    context = format_context(CHUNKS[:2])

    assert context.startswith("[1] (from docker.md)\nDocker images")
    assert "[2] (from redis.md)\nRedis is" in context


def test_cited_sources_maps_numbers_to_unique_sources_in_order():
    text = "Images are templates [1][3]. Redis is in memory [2]."

    assert cited_sources(text, CHUNKS) == ["/notes/docker.md", "/notes/redis.md"]


def test_cited_sources_ignores_out_of_range_numbers():
    assert cited_sources("Made up [7].", CHUNKS) == []


def test_answer_uses_model_output_and_cited_sources():
    llm = FakeListChatModel(responses=["  Redis keeps data in memory [2].  "])

    answer = answer_question("What is Redis?", CHUNKS, llm)

    assert answer.text == "Redis keeps data in memory [2]."
    assert answer.sources == ["/notes/redis.md"]


def test_not_found_answer_has_no_sources():
    llm = FakeListChatModel(responses=["It is not in your documents."])

    answer = answer_question("What's the weather?", CHUNKS, llm)

    assert answer.sources == []
    assert answer.references == []


def test_no_chunks_skips_the_model():
    llm = FakeListChatModel(responses=[])  # would fail if it were called

    answer = answer_question("今天天气怎么样？", [], llm)

    assert answer.text == "你的文档里没有找到相关内容。"
    assert answer.sources == []
    assert answer.references == []


def test_not_found_message_follows_question_language():
    assert not_found_message("今天天气怎么样？") == "你的文档里没有找到相关内容。"
    assert (
        not_found_message("What's the weather?")
        == "I couldn't find this in your documents."
    )


def test_chat_model_factory_turns_thinking_off():
    llm = get_chat_model(
        "some-model", "http://localhost:1234/v1", SecretStr("x"), 0.2, "none"
    )

    assert llm.reasoning_effort == "none"
    assert llm.temperature == 0.2


def test_format_context_distinguishes_passage_numbers_from_pdf_pages():
    chunks = [
        Document(
            page_content="First passage",
            metadata={"source": "/notes/lab.pdf", "page": 7},
        ),
        Document(
            page_content="Second passage",
            metadata={"source": "/notes/lab.pdf", "page": 12},
        ),
        make_chunk("Text note", "/notes/note.md"),
    ]

    context = format_context(chunks)

    assert context == (
        "[1] (from lab.pdf, page 7)\nFirst passage\n\n"
        "[2] (from lab.pdf, page 12)\nSecond passage\n\n"
        "[3] (from note.md)\nText note"
    )
    assert chunks[0].metadata["source"] == "/notes/lab.pdf"


def test_cited_references_preserves_order_and_distinct_pages():
    chunks = [
        Document(
            page_content=f"Passage {index}",
            metadata={"source": "/notes/lab.pdf", "page": page},
        )
        for index, page in enumerate([7, 12, 7], start=1)
    ]
    chunks.append(make_chunk("Text note", "/notes/note.md"))

    references = cited_references("[2][1][3][4][0][99]", chunks)

    assert references == [
        Citation(source="/notes/lab.pdf", page=12),
        Citation(source="/notes/lab.pdf", page=7),
        Citation(source="/notes/note.md"),
    ]


def test_cited_references_without_citations_is_empty():
    assert cited_references("Not found.", CHUNKS) == []


def test_answer_preserves_paths_and_page_references():
    chunks = [
        Document(
            page_content=f"Content on page {page}",
            metadata={"source": "/notes/lab.pdf", "page": page},
        )
        for page in (7, 12)
    ]
    llm = FakeListChatModel(responses=["Two facts [2][1]."])

    answer = answer_question("What are the facts?", chunks, llm)

    assert answer.sources == ["/notes/lab.pdf"]
    assert answer.references == [
        Citation(source="/notes/lab.pdf", page=12),
        Citation(source="/notes/lab.pdf", page=7),
    ]


def test_format_context_includes_epub_section():
    chunk = Document(
        page_content="Beta",
        metadata={"source": "/notes/book.epub", "section": "b.xhtml"},
    )

    assert format_context([chunk]) == ("[1] (from book.epub, section b.xhtml)\nBeta")


def test_answer_preserves_distinct_section_references():
    chunks = [
        Document(
            page_content=f"Content from {section}",
            metadata={"source": "/notes/book.epub", "section": section},
        )
        for section in ["a.xhtml", "b.xhtml", "a.xhtml"]
    ]
    llm = FakeListChatModel(responses=["Two facts [2][1][3]."])

    answer = answer_question("What are the facts?", chunks, llm)

    assert answer.sources == ["/notes/book.epub"]
    assert answer.references == [
        Citation(source="/notes/book.epub", section="b.xhtml"),
        Citation(source="/notes/book.epub", section="a.xhtml"),
    ]
