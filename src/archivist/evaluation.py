"""Load evaluation datasets and run individual cases."""

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal, Self

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

from archivist.loaders import find_files
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


def source_recall(
    expected_sources: list[str],
    retrieved_sources: list[str],
) -> float | None:
    """Return source recall, or None when no sources are expected."""
    expected = set(expected_sources)
    if not expected:
        return None

    retrieved = set(retrieved_sources)
    return len(expected & retrieved) / len(expected)


class AnswerReview(BaseModel):
    """Manual judgments for one saved answer."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyText
    answer_snapshot: str
    cited_sources_snapshot: list[str]
    correctness: bool
    completeness: bool
    citations: bool
    reason: NonEmptyText


class ReviewFile(BaseModel):
    """Manual reviews associated with one evaluation run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    run_file: NonEmptyText
    rubric_version: Literal["1"]
    reviews: list[AnswerReview] = Field(min_length=1)


def load_reviews(review_path: Path, results_path: Path) -> ReviewFile:
    """Load reviews and verify their association with saved answers."""
    data = ReviewFile.model_validate_json(review_path.read_text(encoding="utf-8"))

    if data.run_file != results_path.name:
        raise ValueError("Review run_file does not match results file")

    rows = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
    ]

    by_id = {}
    for row in rows:
        if row["id"] in by_id:
            raise ValueError(f"Duplicate result ID: {row['id']}")
        by_id[row["id"]] = row

    seen: set[str] = set()
    for review in data.reviews:
        if review.id in seen:
            raise ValueError(f"Duplicate review ID: {review.id}")
        seen.add(review.id)

        if review.id not in by_id:
            raise ValueError(f"Unknown review ID: {review.id}")
        row = by_id[review.id]

        if review.answer_snapshot != row["answer"]:
            raise ValueError(f"Answer snapshot mismatch: {review.id}")
        if review.cited_sources_snapshot != row["cited_sources"]:
            raise ValueError(f"Citation snapshot mismatch: {review.id}")

    return data


@dataclass
class ReviewSummary:
    """Counts for reviewed answers and remaining cases."""

    total: int
    reviewed: int
    passed: dict[str, int]
    all_passed: int
    pending: list[str]


def summarize_reviews(cases: list[EvalCase], data: ReviewFile) -> ReviewSummary:
    """Summarize judgments without reading files or printing."""
    case_ids = [case.id for case in cases]
    if not case_ids:
        raise ValueError("Expected a non-empty dataset")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Duplicate dataset IDs")

    review_ids = [review.id for review in data.reviews]
    reviewed_ids = set(review_ids)
    if len(reviewed_ids) != len(review_ids):
        raise ValueError("Duplicate review IDs")
    if not reviewed_ids.issubset(case_ids):
        raise ValueError("Reviews contain unknown dataset IDs")

    return ReviewSummary(
        total=len(cases),
        reviewed=len(data.reviews),
        passed={
            field: sum(getattr(review, field) for review in data.reviews)
            for field in ("correctness", "completeness", "citations")
        },
        all_passed=sum(
            review.correctness and review.completeness and review.citations
            for review in data.reviews
        ),
        pending=[case_id for case_id in case_ids if case_id not in reviewed_ids],
    )


@dataclass
class EvalFingerprints:
    """Content fingerprints for cases and supported corpus files."""

    cases_sha256: str
    corpus_sha256: str
    files: dict[str, str]


def fingerprint_eval_data(cases_path: Path, corpus_dir: Path) -> EvalFingerprints:
    """Hash dataset bytes and corpus-relative filenames/content."""
    files = {
        path.relative_to(corpus_dir).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in find_files(corpus_dir)
    }
    if not files:
        raise ValueError("Evaluation corpus contains no supported files")

    encoded = json.dumps(files, sort_keys=True).encode("utf-8")

    return EvalFingerprints(
        cases_sha256=sha256(cases_path.read_bytes()).hexdigest(),
        corpus_sha256=sha256(encoded).hexdigest(),
        files=files,
    )
