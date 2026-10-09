"""Command-line interface for Archivist."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from langchain_chroma import Chroma
from openai import APIConnectionError

from archivist import pipeline
from archivist.config import Settings, get_settings
from archivist.indexing import get_embeddings, get_vector_store
from archivist.qa import get_chat_model

app = typer.Typer(
    help="Archivist: ask questions about your own documents.",
    no_args_is_help=True,
)


def open_vector_store(settings: Settings) -> Chroma:
    """Open the persistent vector store described by `settings`."""
    embeddings = get_embeddings(
        settings.embedding_model, settings.llm_base_url, settings.llm_api_key
    )
    return get_vector_store(embeddings, settings.storage_dir / "chroma")


@contextmanager
def model_server_errors(settings: Settings) -> Iterator[None]:
    """Turn "model server not running" into a one-line error instead of a traceback."""
    try:
        yield
    except APIConnectionError:
        typer.echo(
            f"Error: cannot reach the model server at {settings.llm_base_url}. "
            "Is the model server running? (e.g. `lms server start`)",
            err=True,
        )
        raise typer.Exit(code=1) from None


@app.callback()
def main() -> None:
    """Archivist: ask questions about your own documents."""


@app.command()
def config() -> None:
    """Show the effective configuration."""
    settings = get_settings()
    for name, value in settings.model_dump().items():
        typer.echo(f"{name} = {value}")


@app.command()
def ingest(
    path: Annotated[
        Path, typer.Argument(exists=True, help="File or directory to ingest.")
    ],
) -> None:
    """Load, split, embed and store documents so they can be searched."""
    settings = get_settings()
    with model_server_errors(settings):
        result = pipeline.ingest(
            path,
            open_vector_store(settings),
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    typer.echo(f"Ingested {result.documents} documents ({result.chunks} chunks).")


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Your question.")],
    top_k: Annotated[
        int | None, typer.Option(min=1, help="Chunks to retrieve (default: config).")
    ] = None,
) -> None:
    """Answer a question from your documents, with sources."""
    settings = get_settings()
    llm = get_chat_model(
        settings.chat_model,
        settings.llm_base_url,
        settings.llm_api_key,
        settings.chat_temperature,
        settings.chat_reasoning_effort,
    )
    with model_server_errors(settings):
        answer = pipeline.ask(
            question,
            open_vector_store(settings),
            llm,
            k=top_k or settings.retrieval_top_k,
            max_distance=settings.retrieval_max_distance,
        )
    typer.echo(answer.text)
    if answer.sources:
        typer.echo("\nSources:")
        for source in answer.sources:
            typer.echo(f"  - {source}")
