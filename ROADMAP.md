# Roadmap

Living plan for **Archivist**. Requirements and conventions live in [AGENTS.md](AGENTS.md).
Update this file whenever the plan changes, and add an entry to the [Changelog](#changelog).

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done · ⏸️ Deferred

| Milestone | Title                          | Status | Branch                         |
|-----------|--------------------------------|--------|--------------------------------|
| M0        | Project scaffolding            | 🟡     | `chore/project-scaffolding`    |
| M1        | Minimal RAG pipeline (MD/TXT)  | ⬜     | `feat/minimal-rag-pipeline`    |
| M2        | Evaluation baseline            | ⬜     | `feat/eval-baseline`           |
| M3        | Multi-format ingestion         | ⬜     | `feat/multi-format-loaders`    |
| M4        | Agentic RAG with LangGraph     | ⬜     | `feat/langgraph-agent`         |
| M5        | Retrieval quality              | ⬜     | `feat/retrieval-improvements`  |
| M6        | Web UI (Streamlit)             | ⬜     | `feat/streamlit-ui`            |

Large milestones may be split into several smaller branches; record them under the milestone.

---

## M0 — Project scaffolding 🟡

**Goal:** a clean, reproducible Python project that runs an empty CLI and an empty test suite.
**Learning focus:** `uv` workflow, `src/` layout, config & secrets handling.

- [x] Initialize `uv` project with a pinned Python (3.13)
- [ ] `pyproject.toml` with project metadata and a console-script entry point
  - [x] Entry point declared; runtime deps `typer`, `pydantic-settings`; dev deps `pytest`, `ruff`
  - [ ] Real `description` (still the uv placeholder)
  - [ ] Entry point wired to a Typer app (currently uv's hello-world `main`)
- [ ] `src/archivist/` package skeleton and `tests/` (package exists; `tests/` not yet)
- [x] `.gitignore` (venv, caches, `.env`, `data/`, `storage/`)
- [x] `.env.example` (`OPENAI_API_KEY`, optional LangSmith vars)
- [x] README with setup and dev commands
- [ ] Config module that loads settings from env
- [ ] ruff + pytest configured; one trivial passing test

**Done when:** `uv run archivist --help` works and `uv run pytest` passes.

---

## M1 — Minimal RAG pipeline (MD/TXT) ⬜

**Goal:** end-to-end RAG on plain-text documents from the CLI.
**Learning focus:** Documents, text splitters, embeddings, vector stores, retrievers, prompt + LLM chain (LCEL).

- [ ] Load `.md` / `.txt` files (single file and directory)
- [ ] Split into chunks; keep `source` metadata on every chunk
- [ ] Embed with OpenAI and persist to Chroma
- [ ] Build a retriever (top-k similarity)
- [ ] Answer chain: grounded prompt, "I don't know" fallback, cite sources
- [ ] CLI: `archivist ingest <path>`, `archivist ask "<question>"`
- [ ] Unit tests for loading/splitting (no network)

**Done when:** ingesting a folder of notes and asking a question returns a grounded answer with sources.

---

## M2 — Evaluation baseline ⬜

**Goal:** measure quality before optimizing, so later changes are comparable.
**Learning focus:** LangSmith tracing, datasets, evaluators.

- [ ] Enable LangSmith tracing via env vars
- [ ] Small golden dataset (10–20 Q&A pairs over a sample corpus)
- [ ] Retrieval check (is the expected source retrieved?) and answer check (LLM-as-judge or reference match)
- [ ] Record baseline scores in this file

**Done when:** one command runs the eval and baseline numbers are recorded.

---

## M3 — Multi-format ingestion ⬜

**Goal:** ingest all target formats with rich metadata and incremental indexing.
**Learning focus:** document loaders, metadata design, idempotent pipelines.

- [ ] Loader registry keyed by file extension
- [ ] PDF loader (page numbers in metadata)
- [ ] DOCX loader
- [ ] HTML loader (strip boilerplate)
- [ ] EPUB loader (chapter/section metadata)
- [ ] Metadata: `file_type`, `page`/`section`, `ingested_at`, `content_hash`
- [ ] Document registry + content-hash dedup; replace chunks of changed files
- [ ] CLI: `archivist list`, `archivist remove <source>`
- [ ] Re-run M2 eval

**Done when:** a mixed-format folder ingests cleanly, re-ingesting is a no-op, and citations show page/section.

---

## M4 — Agentic RAG with LangGraph ⬜

**Goal:** replace the linear chain with a LangGraph agent and support multi-turn chat.
**Learning focus:** state, nodes, edges, conditional routing, tools, checkpointers / memory.

- [ ] Define graph state (messages, retrieved docs, etc.)
- [ ] Retriever as a tool; agent decides whether to retrieve
- [ ] Document relevance grading node
- [ ] Query rewrite node + loop with a retry limit
- [ ] Answer generation node with citations
- [ ] Multi-turn memory via checkpointer (thread id per session)
- [ ] CLI: `archivist chat`
- [ ] Re-run M2 eval and compare with M1/M3

**Done when:** follow-up questions work in `chat` and eval is not worse than the chain baseline.

---

## M5 — Retrieval quality ⬜

**Goal:** improve answer quality using measured experiments.
**Learning focus:** chunking strategies, MMR, hybrid search, reranking, metadata filtering.

- [ ] Chunk size / overlap experiments (format-aware splitting, e.g. Markdown headers)
- [ ] MMR retrieval
- [ ] Hybrid retrieval (BM25 + vectors)
- [ ] Reranking step
- [ ] Metadata filters (by file type / source)
- [ ] Record each experiment's eval result here

**Done when:** at least one change shows a measurable improvement and is kept as the default.

---

## M6 — Web UI (Streamlit) ⬜

**Goal:** a simple local web interface over the same core modules.
**Learning focus:** separating core logic from interfaces, streaming responses.

- [ ] File upload → ingestion
- [ ] Chat view with streaming answers
- [ ] Show cited sources per answer
- [ ] Document list / remove

**Done when:** everything doable in the CLI is doable in the UI.

---

## Backlog ⏸️

- OCR for scanned PDFs
- More formats (PPTX, CSV/XLSX, images)
- LangGraph Studio / LangGraph server deployment
- Optional local-model support (e.g. Ollama)
- Watch a folder and auto-ingest changes

---

## Changelog

- **2026-10-05** — Default branch is `master` (not `main`); AGENTS.md git workflow updated.
  Remaining M0 work continues on `chore/project-scaffolding`. OpenAI API not yet funded —
  not needed for M0; M1 will keep loading/splitting and tests offline (fake embeddings) until it is.

- **2026-10-05** — M0 started. Chose `pydantic-settings` for configuration; M0 deps limited to
  `typer`, `pydantic-settings` (runtime) and `pytest`, `ruff` (dev). LangChain deps deferred to M1.

- **2026-10-05** — Initial roadmap: milestones M0–M6 and backlog defined. Decisions: OpenAI for LLM
  and embeddings, Chroma as vector store, CLI first then Streamlit, docs in English.
