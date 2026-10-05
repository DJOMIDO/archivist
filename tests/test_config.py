import pytest
from pydantic import ValidationError

from archivist.config import Settings


def test_defaults():
    settings = Settings(_env_file=None)
    assert settings.retrieval_top_k == 4
    assert settings.chunk_overlap < settings.chunk_size


def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("ARCHIVIST_CHUNK_SIZE", "500")
    settings = Settings(_env_file=None)
    assert settings.chunk_size == 500


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValidationError, match="chunk_overlap"):
        Settings(_env_file=None, chunk_size=100, chunk_overlap=100)
