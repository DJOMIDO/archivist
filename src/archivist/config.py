from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="ARCHIVIST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Model server (any OpenAI-compatible API: LM Studio, mlx-lm, llama.cpp) ---
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: SecretStr = SecretStr("not-needed")

    # --- Models ---
    chat_model: str = "qwen/qwen3.5-9b"
    chat_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    chat_reasoning_effort: str | None = "none"
    embedding_model: str = "text-embedding-qwen3-embedding-0.6b"

    # --- Chunking (sizes are in characters, not tokens) ---
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)

    # --- Retrieval ---
    retrieval_top_k: int = Field(default=4, gt=0, le=20)
    retrieval_max_distance: float | None = Field(default=None, gt=0)

    # --- Paths ---
    data_dir: Path = Path("data")
    storage_dir: Path = Path("storage")

    @model_validator(mode="after")
    def _check_chunking(self) -> Self:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be smaller than "
                f"chunk_size ({self.chunk_size})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
