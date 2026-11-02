import json
from unittest.mock import Mock

import pytest
from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError

from archivist.evaluation import (
    REFERENCE_JUDGE_PROMPT,
    EvalCase,
    ReferenceGrade,
    grade_reference,
    iter_reference_grades,
)


@pytest.fixture
def judge_case():
    return EvalCase(
        id="judge-001",
        question="Which model is used?",
        answerable=False,
        reference_answer="The documents do not specify a model.",
        expected_sources=[],
    )


@pytest.mark.parametrize("decision", [True, False])
def test_grade_reference_sends_inputs_and_preserves_verdict(judge_case, decision):
    llm = Mock(spec=BaseChatModel)
    expected = ReferenceGrade(
        matches_reference=decision,
        reason="Stub decision for a code test.",
    )
    structured = llm.with_structured_output.return_value
    structured.invoke.return_value = expected
    candidate = "The documents do not specify a model."

    result = grade_reference(judge_case, candidate, llm)

    assert result is expected
    llm.with_structured_output.assert_called_once_with(
        ReferenceGrade, method="json_schema", strict=True
    )
    structured.invoke.assert_called_once()

    messages = structured.invoke.call_args.args[0]
    assert messages[0] == ("system", REFERENCE_JUDGE_PROMPT)
    assert messages[1][0] == "human"
    assert json.loads(messages[1][1]) == {
        "question": judge_case.question,
        "answerable": False,
        "reference_answer": judge_case.reference_answer,
        "candidate_answer": candidate,
    }


def test_judge_failure_is_not_converted_to_a_failed_grade(judge_case):
    llm = Mock(spec=BaseChatModel)
    llm.with_structured_output.return_value.invoke.side_effect = RuntimeError(
        "judge unavailable"
    )

    with pytest.raises(RuntimeError, match="judge unavailable"):
        grade_reference(judge_case, "Candidate answer", llm)


@pytest.mark.parametrize(
    "changes",
    [
        {"matches_reference": "false"},
        {"reason": ""},
        {"unexpected": 1},
    ],
    ids=["string-bool", "empty-reason", "extra-field"],
)
def test_reject_invalid_grade_fields(changes):
    values = {
        "matches_reference": True,
        "reason": "A non-empty explanation.",
        **changes,
    }

    with pytest.raises(ValidationError):
        ReferenceGrade.model_validate(values)


@pytest.fixture
def batch_inputs(judge_case):
    second = EvalCase.model_validate({**judge_case.model_dump(), "id": "judge-002"})
    cases = [judge_case, second]
    answers = {
        second.id: "Second candidate",
        judge_case.id: "First candidate",
    }
    return cases, answers


def test_batch_yields_ordered_snapshots_and_preserves_false(batch_inputs):
    cases, answers = batch_inputs
    llm = Mock(spec=BaseChatModel)
    llm.with_structured_output.return_value.invoke.side_effect = [
        ReferenceGrade(matches_reference=True, reason="First stub verdict."),
        ReferenceGrade(matches_reference=False, reason="Second stub verdict."),
    ]

    grades = iter_reference_grades(cases, answers, llm)
    llm.with_structured_output.assert_not_called()
    rows = list(grades)

    assert [row.id for row in rows] == [case.id for case in cases]
    assert [row.grade.matches_reference for row in rows] == [True, False]
    for case, row in zip(cases, rows, strict=True):
        assert row.question == case.question
        assert row.answerable == case.answerable
        assert row.answer_snapshot == answers[case.id]
        assert row.reference_answer_snapshot == case.reference_answer
    assert llm.with_structured_output.return_value.invoke.call_count == 2
    assert rows[1].model_dump(mode="json")["grade"]["matches_reference"] is False


def test_batch_propagates_failure_after_yielding_first_grade(batch_inputs):
    cases, answers = batch_inputs
    llm = Mock(spec=BaseChatModel)
    llm.with_structured_output.return_value.invoke.side_effect = [
        ReferenceGrade(matches_reference=False, reason="First stub verdict."),
        RuntimeError("second request failed"),
    ]
    grades = iter_reference_grades(cases, answers, llm)

    first = next(grades)
    assert first.id == cases[0].id
    assert first.grade.matches_reference is False
    with pytest.raises(RuntimeError, match="second request failed"):
        next(grades)


@pytest.mark.parametrize("problem", ["missing", "extra"])
def test_batch_rejects_mismatched_answer_ids(batch_inputs, problem):
    cases, answers = batch_inputs
    if problem == "missing":
        answers.pop(cases[-1].id)
    else:
        answers["unknown"] = "Unexpected answer"
    llm = Mock(spec=BaseChatModel)

    with pytest.raises(ValueError, match="Answer IDs do not match"):
        list(iter_reference_grades(cases, answers, llm))
    llm.with_structured_output.assert_not_called()


def test_batch_rejects_empty_dataset():
    llm = Mock(spec=BaseChatModel)

    with pytest.raises(ValueError, match="non-empty dataset"):
        list(iter_reference_grades([], {}, llm))
    llm.with_structured_output.assert_not_called()


def test_batch_rejects_duplicate_case_ids(judge_case):
    llm = Mock(spec=BaseChatModel)

    with pytest.raises(ValueError, match="Duplicate dataset IDs"):
        list(
            iter_reference_grades(
                [judge_case, judge_case],
                {judge_case.id: "Candidate"},
                llm,
            )
        )
    llm.with_structured_output.assert_not_called()
