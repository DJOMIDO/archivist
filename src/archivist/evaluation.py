"""Load evaluation datasets and run individual cases."""

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Annotated, Self

from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

from archivist.qa import answer_question
from archivist.retrieval import retrieve

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EvalCase(BaseModel):
    """One question and its reference expectations."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyText
    question: NonEmptyText
    answerable: bool
    reference_answer: NonEmptyText
    expected_sources: list[NonEmptyText]

    @model_validator(mode="after")
    def check_sources(self) -> Self:
        if bool(self.expected_sources) != self.answerable:
            raise ValueError("Sources contradict answerable")
        return self


CASE_LIST = TypeAdapter(Annotated[list[EvalCase], Field(min_length=1)])


def load_eval_cases(path: Path, corpus_dir: Path) -> list[EvalCase]:
    """Read cases and verify their IDs and source files."""
    cases = CASE_LIST.validate_json(path.read_text(encoding="utf-8"))
    corpus_root = corpus_dir.resolve()
    seen: set[str] = set()

    for case in cases:
        if case.id in seen:
            raise ValueError(f"Duplicate ID: {case.id}")
        seen.add(case.id)

        for source in case.expected_sources:
            relative = Path(source)
            resolved = (corpus_root / relative).resolve()

            if relative.is_absolute() or not resolved.is_relative_to(corpus_root):
                raise ValueError(f"{case.id}: source must stay inside corpus: {source}")

            if not resolved.is_file():
                raise FileNotFoundError(f"{case.id}: missing source: {source}")

    return cases


@dataclass
class RetrievedSource:
    """One retrieved passage's source and distance."""

    source: str
    distance: float


@dataclass
class EvalResult:
    """Raw output and timings for one evaluation case."""

    id: str
    question: str
    retrieved: list[RetrievedSource]
    answer: str
    cited_sources: list[str]
    retrieve_seconds: float
    generate_seconds: float


def run_eval_case(
    case: EvalCase,
    vector_store: VectorStore,
    llm: BaseChatModel,
    corpus_dir: Path,
    k: int,
    max_distance: float | None = None,
) -> EvalResult:
    """Retrieve once, generate an answer, and record raw results."""
    corpus = corpus_dir.resolve()

    started = perf_counter()
    hits = retrieve(vector_store, case.question, k=k, max_distance=max_distance)
    retrieved = perf_counter()

    answer = answer_question(case.question, [doc for doc, _ in hits], llm)
    finished = perf_counter()

    return EvalResult(
        id=case.id,
        question=case.question,
        retrieved=[
            RetrievedSource(
                source=Path(doc.metadata["source"])
                .resolve()
                .relative_to(corpus)
                .as_posix(),
                distance=float(distance),
            )
            for doc, distance in hits
        ],
        answer=answer.text,
        cited_sources=[
            Path(source).resolve().relative_to(corpus).as_posix()
            for source in answer.sources
        ],
        retrieve_seconds=retrieved - started,
        generate_seconds=finished - retrieved,
    )
