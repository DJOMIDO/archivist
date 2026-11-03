import pytest
from pydantic import ValidationError

from archivist.index_profile import IndexProfile, fingerprint_index_profile


@pytest.fixture
def profile() -> IndexProfile:
    return IndexProfile(
        embedding_model="test-embedding",
        embedding_base_url="http://localhost:1234/v1",
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "。", " ", ""],
        python="3.13.5",
        packages={"pypdf": "6.0.0", "ebooklib": "0.20"},
    )


def test_profile_json_round_trip_and_fingerprint(profile: IndexProfile):
    restored = IndexProfile.model_validate_json(profile.model_dump_json())

    assert restored == profile
    assert fingerprint_index_profile(restored) == (
        "5e59d6553b2f76c4a30654704af37c3cff40e37a17269c56f8fbb8942e1d05be"
    )


def test_profile_fingerprint_ignores_dictionary_order(profile: IndexProfile):
    data = dict(reversed(list(profile.model_dump().items())))
    data["packages"] = dict(reversed(list(profile.packages.items())))

    reordered = IndexProfile.model_validate(data)

    assert fingerprint_index_profile(reordered) == fingerprint_index_profile(profile)


@pytest.mark.parametrize(
    "changes",
    [
        {"embedding_model": "other-embedding"},
        {"embedding_base_url": "http://localhost:4321/v1"},
        {"chunk_size": 800},
        {"chunk_overlap": 100},
        {"separators": ["", " ", "。", "\n\n"]},
        {"pipeline_revision": "ingestion-v2"},
        {"python": "3.13.6"},
        {"packages": {"pypdf": "6.0.1", "ebooklib": "0.20"}},
    ],
)
def test_index_changes_affect_fingerprint(
    profile: IndexProfile, changes: dict[str, object]
):
    changed = IndexProfile.model_validate({**profile.model_dump(), **changes})

    assert fingerprint_index_profile(changed) != fingerprint_index_profile(profile)


@pytest.mark.parametrize(
    "changes",
    [
        {"chunk_size": 0},
        {"chunk_size": True},
        {"chunk_size": "1000"},
        {"chunk_overlap": -1},
        {"chunk_overlap": 1000},
        {"schema_version": 2},
        {"llm_api_key": "test-value"},
        {"chat_temperature": 0.5},
    ],
)
def test_profile_rejects_invalid_or_unrelated_fields(
    profile: IndexProfile, changes: dict[str, object]
):
    with pytest.raises(ValidationError):
        IndexProfile.model_validate({**profile.model_dump(), **changes})
