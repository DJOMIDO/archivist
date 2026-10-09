from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel
from pydantic import SecretStr

from archivist.qa import (
    answer_question,
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


def test_no_chunks_skips_the_model():
    llm = FakeListChatModel(responses=[])  # would fail if it were called

    answer = answer_question("今天天气怎么样？", [], llm)

    assert answer.text == "你的文档里没有找到相关内容。"
    assert answer.sources == []


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
