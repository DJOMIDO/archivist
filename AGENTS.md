# AGENTS.md

Guidance for AI coding agents (and humans) working on **Archivist**.
Read this file before doing anything in the repo. The plan lives in [ROADMAP.md](ROADMAP.md).

---

## 1. Project overview

**Archivist** is a personal document Q&A assistant built on Retrieval-Augmented Generation (RAG).

- The user imports their own documents in many formats (PDF, Markdown, TXT, DOCX, HTML, EPUB).
- Documents are parsed, split into chunks, embedded, and stored in a local vector store.
- The user asks questions in natural language; an agent retrieves relevant chunks and answers
  **grounded in those documents, with source citations**.

This is primarily a **learning project**: the owner is applying what they learned in
LangChain Academy (LangChain + LangGraph). Understanding *why* matters more than shipping fast.

---

## 2. Learning mode — rules for AI agents

These rules override any default "just write the code" behavior.

1. **Teach in lessons.** The owner knows LangChain basics (LangChain Academy) but has little
   background in the surrounding engineering (packaging, testing, data pipelines). Each step is a
   lesson: **purpose → concepts → code → walkthrough → verify → exercise/thinking question → commit**.
   Within "code", go in three stages: **(a) a minimal standalone script** (a dozen lines, core
   logic only) → **(b) refactor it into the project module**, explaining every addition →
   **(c) tests**. The user should see the simplest form before the production form.
2. **Provide working code, explained.** Give complete, verified code for each step, with a
   walkthrough of *why* each part exists. The user types it in themselves (not copy-paste) and
   then does a small exercise that extends or tests it. Leave room for the user to try first
   when a step is small enough.
3. **Review the user's code** when asked: correctness, LangChain/LangGraph idioms, edge cases,
   naming, testability. Point to the relevant concept or docs rather than silently rewriting.
4. **Call out pitfalls proactively** (e.g., chunk size vs. context window, metadata loss during
   splitting, embedding cost, API-key leakage, non-deterministic tests).
5. **One step at a time.** Break each milestone into small, verifiable steps; confirm a step works
   before moving on.
6. **Language:** talk to the user in **Chinese**; write code, comments, docs, branch names, and
   commit messages in **English**.
7. **Git is the user's job.** Do not create branches or commits. Instead *suggest* a branch name
   and a commit message (see §7) whenever a change warrants it.
8. **Keep the docs alive** (see §8).

---

## 3. Functional requirements

### 3.1 Ingestion
- Supported formats: **PDF, Markdown, TXT, DOCX, HTML, EPUB** (rolled out across milestones).
- Ingest a single file or a whole directory (recursive).
- Attach metadata to every chunk: `source` (path), `file_type`, `page` / `section` when available,
  `ingested_at`, `content_hash`.
- **Incremental indexing:** re-ingesting an unchanged file is a no-op; a changed file replaces its
  old chunks (dedup by content hash).
- List indexed documents and remove a document (and all its chunks) from the index.

### 3.2 Question answering
- Answer natural-language questions using only retrieved context.
- **Cite sources** (file + page/section) for every answer.
- Say "I don't know / not found in your documents" when the context does not support an answer —
  no hallucinated answers.
- Support **multi-turn conversations** (follow-up questions use chat history).

### 3.3 Agent
- Built with **LangGraph** as an agentic RAG: retriever exposed as a tool, the agent decides
  whether to retrieve, grades retrieved documents for relevance, and rewrites the query when
  retrieval is poor.
- Conversation state persisted via a LangGraph checkpointer.

### 3.4 Interfaces
- **CLI first:** `ingest`, `ask`, `chat`, `list`, `remove`.
- **Web UI later:** Streamlit app (upload files, chat, show sources).

---

## 4. Non-functional requirements

- **Local-first & free:** LLM and embeddings run locally behind an OpenAI-compatible server
  (currently LM Studio's headless engine `llmster`, managed with `lms`; no paid API required);
  vector store and document registry persisted on disk.
- **Secrets:** API keys (e.g. LangSmith) come from environment / `.env`; `.env` is never committed
  (provide `.env.example`).
- **Observability:** LangSmith tracing can be toggled via env vars.
- **Testability:** core logic (loading, splitting, indexing, retrieval) is unit-testable without
  network calls; LLM/embedding calls are mockable.
- **Resource awareness:** batch embedding calls, avoid re-embedding unchanged content
  (local models are slow on large corpora).
- **Configurable:** model names, chunk size/overlap, top-k, storage paths live in one config place.

---

## 5. Tech stack

| Concern            | Choice                                                                  |
|--------------------|-------------------------------------------------------------------------|
| Language           | Python **3.12 or 3.13** (pinned via `uv`; 3.14 may lack wheels for some deps) |
| Env / packaging    | `uv` + `pyproject.toml`                                                 |
| Framework          | LangChain, LangGraph                                                    |
| LLM & embeddings   | Any OpenAI-compatible server via `langchain-openai` (base URL in config); currently LM Studio's headless `llmster` on `localhost:1234` |
| Default models     | Chat: `qwen/qwen3.5-9b` (MLX 8-bit, tool calling; thinking off via `reasoning_effort="none"`). Embeddings: `text-embedding-qwen3-embedding-0.6b` (GGUF Q8, 1024-dim, instruction-aware queries). **Changing the embedding model requires rebuilding the index.** |
| Vector store       | Chroma (local persistent) via `langchain-chroma`                        |
| Loaders            | pypdf / PyMuPDF (PDF), docx2txt or Unstructured (DOCX), BeautifulSoup (HTML), EPUB loader; plain readers for MD/TXT |
| Configuration      | pydantic-settings (typed settings from env / `.env`)                    |
| CLI                | Typer                                                                   |
| Web UI (later)     | Streamlit                                                               |
| Quality            | pytest, ruff                                                            |
| Tracing / eval     | LangSmith                                                               |

Pick concrete library versions when a milestone needs them; record notable choices in ROADMAP's changelog.

---

## 6. Proposed architecture

```
archivist/
├── src/archivist/
│   ├── config.py        # settings (env, paths, model names, chunk params)
│   ├── loaders.py       # find + load files as Documents (becomes loaders/ package in M3)
│   ├── splitting.py     # text splitters, metadata preservation
│   ├── indexing.py      # embedding/vector-store factories, stable chunk IDs (registry in M3)
│   ├── retrieval.py     # top-k search with distances (MMR / hybrid in M5)
│   ├── qa.py            # grounded prompt, chat-model factory, citation → source mapping
│   ├── pipeline.py      # wires the steps together; shared by CLI and future web UI
│   ├── agent/           # LangGraph state, nodes, graph, prompts (M4)
│   └── cli.py           # Typer commands: thin layer that reads settings and prints
├── tests/
├── data/                # user documents (git-ignored)
├── storage/             # vector store + registry (git-ignored)
├── AGENTS.md
└── ROADMAP.md
```

Data flow: **load → split → embed → store** (ingestion) and
**question → (rewrite) → retrieve → grade → generate with citations** (query).

Design rules: model/provider details live only in the factory functions (`get_embeddings`,
`get_chat_model`); core functions take their dependencies as arguments and never call
`get_settings()` themselves — only the CLI (the program edge) reads settings.

This layout is a proposal; refine it as milestones are implemented and update this section.

---

## 7. Git workflow

### Branches
- `master` is the default branch and stays runnable.
- Branch name format: `<type>/<short-kebab-description>`, e.g. `feat/minimal-rag-pipeline`,
  `fix/pdf-page-metadata`, `docs/update-roadmap`.
- Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`.
- One concern per branch; merge back into `master` when the step is done.

### Commits — [Conventional Commits](https://www.conventionalcommits.org/)
```
<type>(<optional scope>): <imperative summary, ≤ 72 chars, no period>

<optional body: what and WHY, wrapped at ~72 chars>
```
Examples:
- `feat(loaders): add PDF loader with page metadata`
- `fix(indexing): skip re-embedding unchanged files`
- `docs(roadmap): mark M1 as done`

Small, focused commits; each should leave the project in a working state.

---

## 8. Documentation maintenance

- **ROADMAP.md** must be updated whenever the plan changes: task completed, scope added/removed,
  milestone reordered, or a notable technical decision made (add a changelog entry).
- **AGENTS.md** must be updated whenever requirements, conventions, tech stack, or architecture change.
- Doc updates can ship in the same branch as the related change, or in a `docs/...` branch.
