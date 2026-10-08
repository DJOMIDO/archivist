"""Answer questions from retrieved chunks, citing only the sources actually used."""

import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

NOT_FOUND = {
    "zh": "你的文档里没有找到相关内容。",
    "en": "I couldn't find this in your documents.",
}
CJK = re.compile(r"[\u4e00-\u9fff]")

SYSTEM_PROMPT = """You answer questions using ONLY the numbered context passages below.

Rules:
- Use only facts stated in the context. Never add facts from your own knowledge.
- Cite passage numbers after each sentence that uses them, e.g. [1] or [2][3].
- If the context does not answer the question, say so in one short sentence and
  cite nothing.
- Answer in the same language as the question.

Context:
{context}"""

PROMPT = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "{question}")]
)

CITATION = re.compile(r"\[(\d+)\]")


@dataclass
class Answer:
    text: str
    sources: list[str]


def get_chat_model(model: str, base_url: str, temperature: float) -> BaseChatModel:
    """Create the chat model client (Ollama), with thinking turned off for speed."""
    return ChatOllama(
        model=model, base_url=base_url, temperature=temperature, reasoning=False
    )


def format_context(chunks: list[Document]) -> str:
    """Number each chunk so the model can cite it as [1], [2], ..."""
    return "\n\n".join(
        f"[{i}] (from {Path(chunk.metadata['source']).name})\n{chunk.page_content}"
        for i, chunk in enumerate(chunks, start=1)
    )


def cited_sources(text: str, chunks: list[Document]) -> list[str]:
    """Map the [n] citations in `text` back to chunk sources, unique and in order."""
    sources: list[str] = []
    for match in CITATION.finditer(text):
        index = int(match.group(1))
        if 1 <= index <= len(chunks):
            source = chunks[index - 1].metadata["source"]
            if source not in sources:
                sources.append(source)
    return sources


def not_found_message(question: str) -> str:
    """The "nothing found" reply, in Chinese if the question contains Chinese."""
    return NOT_FOUND["zh" if CJK.search(question) else "en"]


def answer_question(
    question: str, chunks: list[Document], llm: BaseChatModel
) -> Answer:
    """Generate a grounded answer; skip the LLM entirely when nothing was retrieved."""
    if not chunks:
        return Answer(text=not_found_message(question), sources=[])

    chain = PROMPT | llm | StrOutputParser()
    text = chain.invoke(
        {"context": format_context(chunks), "question": question}
    ).strip()
    return Answer(text=text, sources=cited_sources(text, chunks))
