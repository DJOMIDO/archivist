import pytest
from pydantic import ValidationError

from archivist.evaluation import RunParameters


@pytest.fixture
def parameter_values():
    return {
        "chat_variant": "MLX 8-bit",
        "chat_model": "example-chat",
        "chat_temperature": 0.2,
        "chat_reasoning_effort": "none",
        "embedding_model": "example-embedding",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "k": 4,
        "max_distance": None,
    }


@pytest.mark.parametrize("max_distance", [None, 1.2])
def test_parameters_round_trip_through_json(parameter_values, max_distance):
    parameter_values["max_distance"] = max_distance
    parameters = RunParameters.model_validate(parameter_values)

    restored = RunParameters.model_validate_json(parameters.model_dump_json())

    assert restored == parameters
    assert restored.max_distance == max_distance


@pytest.mark.parametrize(
    "changes",
    [
        {"k": 0},
        {"k": 21},
        {"k": "4"},
        {"chunk_overlap": 1000},
        {"max_distance": 0.0},
        {"chat_variant": "   "},
        {"chat_temperature": 2.1},
        {"api_key": "example-key"},
    ],
    ids=[
        "zero-k",
        "excessive-k",
        "string-k",
        "overlap-equals-size",
        "zero-distance",
        "blank-variant",
        "excessive-temperature",
        "unexpected-secret",
    ],
)
def test_reject_invalid_parameters(parameter_values, changes):
    parameter_values.update(changes)

    with pytest.raises(ValidationError):
        RunParameters.model_validate(parameter_values)
