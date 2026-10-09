# Archivist

A personal document Q&A assistant built on Retrieval-Augmented Generation (RAG).
Import your own documents (PDF, Markdown, TXT, DOCX, HTML, EPUB) and ask questions — answers are
grounded in your files and cite their sources.

Built with [LangChain](https://python.langchain.com/) and [LangGraph](https://langchain-ai.github.io/langgraph/)
as a learning project.

> **Status:** M1 done — Markdown/TXT ingestion and grounded Q&A from the CLI. See [ROADMAP.md](ROADMAP.md).

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.13 (installed automatically by uv)
- A local OpenAI-compatible model server. The default setup uses LM Studio's headless engine
  [llmster](https://lmstudio.ai/docs/developer/core/headless) (no desktop app needed):

  ```bash
  curl -fsSL https://lmstudio.ai/install.sh | bash   # installs llmster + the `lms` CLI
  lms get qwen/qwen3.5-9b --mlx                      # chat model (pick the 8-bit MLX build)
  lms get qwen3-embedding-0.6b                       # embedding model (search; pick GGUF Q8)
  lms daemon up && lms server start                  # serve http://localhost:1234/v1
  ```

  Download models with `lms get <hub-name>`, not by copying files: the hub definition is what
  lets `reasoning_effort="none"` turn off "thinking". Without it the chat model is listed under
  its folder name and every answer takes minutes. The server must be running whenever you use
  `ingest` or `ask`; models load on first use and unload after an hour idle.

## Getting started

```bash
uv sync                    # create .venv and install dependencies
cp .env.example .env       # adjust settings if needed
uv run archivist --help
```

## Usage

```bash
uv run archivist ingest data/                       # load, split, embed and store documents
uv run archivist ask "How do I make tomato eggs?"   # answer with cited sources
uv run archivist ask "..." --top-k 2                # override how many chunks are retrieved
uv run archivist config                             # show the effective settings
```

Re-ingesting unchanged files does not create duplicates. Settings can be overridden in `.env`
(see `.env.example`).

## Development

```bash
uv run pytest              # run tests
uv run ruff check .        # lint
uv run ruff format .       # format
```

## Documentation

- [AGENTS.md](AGENTS.md) — requirements, architecture, and conventions
- [ROADMAP.md](ROADMAP.md) — milestones and progress
