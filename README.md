# Archivist

A personal document Q&A assistant built on Retrieval-Augmented Generation (RAG).
Import your own documents (PDF, Markdown, TXT, DOCX, HTML, EPUB) and ask questions — answers are
grounded in your files and cite their sources.

Built with [LangChain](https://python.langchain.com/) and [LangGraph](https://langchain-ai.github.io/langgraph/)
as a learning project.

> **Status:** early development (M0 — project scaffolding). See [ROADMAP.md](ROADMAP.md).

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.13 (installed automatically by uv)
- An OpenAI API key

## Getting started

```bash
uv sync                    # create .venv and install dependencies
cp .env.example .env       # then fill in your API keys
uv run archivist --help
```

## Development

```bash
uv run pytest              # run tests
uv run ruff check .        # lint
uv run ruff format .       # format
```

## Documentation

- [AGENTS.md](AGENTS.md) — requirements, architecture, and conventions
- [ROADMAP.md](ROADMAP.md) — milestones and progress
