"""Load and validate evaluation datasets."""

from pathlib import Path
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

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
