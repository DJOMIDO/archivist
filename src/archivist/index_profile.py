"""Describe index-building conditions and compute their fingerprint."""

import json
from hashlib import sha256
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

INDEX_PACKAGE_NAMES = (
    "langchain-core",
    "langchain-openai",
    "langchain-text-splitters",
    "langchain-chroma",
    "chromadb",
    "pypdf",
    "docx2txt",
    "beautifulsoup4",
    "ebooklib",
    "lxml",
)


class IndexProfile(BaseModel):
    """Explicit index configuration, excluding secrets and query settings."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    pipeline_revision: str = Field(default="ingestion-v1", min_length=1)
    embedding_model: str = Field(min_length=1)
    embedding_base_url: str = Field(min_length=1)
    chunk_size: int = Field(gt=0)
    chunk_overlap: int = Field(ge=0)
    separators: list[str]
    python: str = Field(min_length=1)
    packages: dict[str, str]

    @model_validator(mode="after")
    def check_chunking(self) -> Self:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


def fingerprint_index_profile(profile: IndexProfile) -> str:
    """Return a deterministic SHA-256 digest of the profile."""
    serialized = json.dumps(
        profile.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()
