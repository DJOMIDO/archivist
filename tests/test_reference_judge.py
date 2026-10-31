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
