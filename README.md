# Archivist

A personal document Q&A assistant built on Retrieval-Augmented Generation (RAG).
Import your own documents (PDF, Markdown, TXT, DOCX, HTML, EPUB) and ask questions — answers are
grounded in your files and cite their sources.

Built with [LangChain](https://python.langchain.com/) and [LangGraph](https://langchain-ai.github.io/langgraph/)
as a learning project.

> **Status:** M2 done — Markdown/TXT RAG with a reproducible evaluation baseline. See [ROADMAP.md](ROADMAP.md).

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

## Evaluation

The baseline contains 12 questions over six fictional Cedar Notes documents in
`evals/`. Run commands from the repository root with the local model server running.

The following example uses this machine's verified single-variant model definition,
`archivist/qwen35-8bit`. It is configured in LM Studio locally and is not installed
by cloning this repository. On another machine, substitute an available API model
identifier and verify its loaded quantization. An unqualified Hub name can select
a different variant; `--chat-variant` and `--judge-variant` are descriptive labels.

```bash
uv run python scripts/validate_eval.py
lms ps --json                 # inspect loaded quantization, context and parallelism
uv run python scripts/eval_all.py \
  --chat-model archivist/qwen35-8bit \
  --chat-variant "MLX 8-bit" \
  --judge-model archivist/qwen35-8bit \
  --judge-variant "MLX 8-bit"
```

The unified command creates a fresh `storage/eval-runs/<run-id>/` directory,
indexes a snapshot of the corpus, generates answers, grades them, and saves a
validated `report.json`. Artifacts include:

- `inputs/`: case and corpus snapshots used for this run.
- `manifest.json`: parameters, fingerprints, software versions, and run status.
- `results.jsonl`: answers, retrieved passages, cited sources, and timings.
- `reference-grades/<batch-id>/`: grades and judge/rubric provenance.
- `report.json`: source recall, reference matches, and mean timings.

`storage/` is Git-ignored. Preserve completed runs; use fresh runs for changed
models or data. The report checks hashes, IDs, snapshots, and completed statuses.
To recompute an existing report without model calls, replace the two placeholders:

```bash
uv run python scripts/report_eval.py \
  storage/eval-runs/<run-id> \
  storage/eval-runs/<run-id>/reference-grades/<batch-id>
```

For memory-constrained comparisons, run preparation, generation, grading, and
reporting separately so you can unload the candidate before loading the judge:

```bash
ARCHIVIST_CHAT_MODEL=archivist/qwen35-4bit \
uv run python scripts/prepare_eval_run.py --chat-variant "MLX 4-bit"
# Use the newly printed run directory below.
uv run python scripts/run_eval.py storage/eval-runs/<run-id>
# Switch to the verified 8-bit judge in the model server before grading.
ARCHIVIST_CHAT_MODEL=archivist/qwen35-8bit \
uv run python scripts/judge_batch.py storage/eval-runs/<run-id> \
  --judge-variant "MLX 8-bit"
```

The local `archivist/qwen35-4bit` definition has the same machine-specific setup
requirement as the 8-bit definition. Record actual loaded settings before each
stage: MLX auto-fit overrode the requested context length in our comparison.
Use the same judge and data when comparing candidates. Source recall measures
retrieval coverage; reference matching is a model verdict and does not score
citation accuracy. Single-run timings without controlled warm-up are descriptive.
The verified comparison and its limitations are recorded in [ROADMAP.md](ROADMAP.md).

## Development

```bash
uv run pytest              # run tests
uv run ruff check .        # lint
uv run ruff format .       # format
```

## Documentation

- [AGENTS.md](AGENTS.md) — requirements, architecture, and conventions
- [ROADMAP.md](ROADMAP.md) — milestones and progress
