# Roadmap

Living plan for **Archivist**. Requirements and conventions live in [AGENTS.md](AGENTS.md).
Update this file whenever the plan changes, and add an entry to the [Changelog](#changelog).

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done · ⏸️ Deferred

| Milestone | Title                          | Status | Branch                         |
|-----------|--------------------------------|--------|--------------------------------|
| M0        | Project scaffolding            | ✅     | `chore/project-scaffolding`    |
| M1        | Minimal RAG pipeline (MD/TXT)  | ✅     | `feat/minimal-rag-pipeline`    |
| M1.5      | Local model runtime evaluation | ✅     | `refactor/openai-compatible-llm-provider` |
| M2        | Evaluation baseline            | 🟡     | `feat/eval-baseline`           |
| M3        | Multi-format ingestion         | ⬜     | `feat/multi-format-loaders`    |
| M4        | Agentic RAG with LangGraph     | ⬜     | `feat/langgraph-agent`         |
| M5        | Retrieval quality              | ⬜     | `feat/retrieval-improvements`  |
| M6        | Web UI (Streamlit)             | ⬜     | `feat/streamlit-ui`            |

Large milestones may be split into several smaller branches; record them under the milestone.

---

## M0 — Project scaffolding ✅

**Goal:** a clean, reproducible Python project that runs an empty CLI and an empty test suite.
**Learning focus:** `uv` workflow, `src/` layout, config & secrets handling.

- [x] Initialize `uv` project with a pinned Python (3.13)
- [x] `pyproject.toml` with metadata, deps and console-script entry point (`archivist.cli:app`)
- [x] `src/archivist/` package skeleton and `tests/`
- [x] `.gitignore` (venv, caches, `.env`, `data/`, `storage/`)
- [x] `.env.example` (Ollama URL, model, chunking, retrieval settings; optional LangSmith vars)
- [x] README with setup and dev commands
- [x] Config module (`pydantic-settings`, `ARCHIVIST_` prefix, range + cross-field validation)
- [x] Typer CLI skeleton with `config` command
- [x] ruff + pytest configured; config and CLI tests (settings cache cleared per test)
- [x] VS Code workspace settings: format on save with Ruff

**Done when:** `uv run archivist --help` works and `uv run pytest` passes.

---

## M1 — Minimal RAG pipeline (MD/TXT) ✅

**Goal:** end-to-end RAG on plain-text documents from the CLI.
**Learning focus:** Documents, text splitters, embeddings, vector stores, retrievers, prompt + LLM chain (LCEL).

- [x] Load `.md` / `.txt` files (single file and directory; hidden files/dirs skipped)
- [x] Split into chunks (Chinese/English sentence separators); keep `source` + `start_index` metadata
- [x] Install Ollama and pull a chat model and an embedding model
- [x] Embed with Ollama and persist to Chroma (stable chunk IDs → idempotent re-ingest)
- [x] Build a retriever (top-k similarity with distances; optional max-distance cut-off)
- [x] Answer chain: grounded prompt, "not found" fallback (zh/en), citations mapped to sources in code
- [x] CLI: `archivist ingest <path>`, `archivist ask "<question>" [--top-k N]` (via `pipeline.py`)
- [x] Tests for every module plus an offline end-to-end pipeline/CLI test (31 tests, no network)

**Done when:** ingesting a folder of notes and asking a question returns a grounded answer with sources.

**Known limitations (deferred):** with `retrieval_max_distance` unset every question reaches the
LLM; the small model sometimes cites passages while saying it found nothing (seen with a French
question); a stopped Ollama shows a raw traceback; sources print as absolute paths.

---

## M1.5 — Local model runtime evaluation ✅

**Goal:** stop depending on Ollama specifically (openness and lock-in concerns) by talking to any
local OpenAI-compatible server.
**Learning focus:** provider abstraction — only the two model factories should change.

- [x] Switch `get_embeddings` / `get_chat_model` to `langchain-openai` with a configurable base URL
  (only the two factories, config and CLI wiring changed; all 31 existing tests passed unchanged)
- [x] Evaluate candidates: LM Studio (GUI closed source), `mlx-lm` server (MIT), llama.cpp
  `llama-server` (MIT) — chose LM Studio's engine (served by Bionic / `lms`); others not needed
- [x] Go/no-go criteria: thinking can be disabled (`reasoning_effort="none"` → 0 reasoning
  tokens), embedding model loads on demand (JIT, 60 min idle TTL), API runs as a background
  service (`--run-as-service`) without a window. Generation is ~8–11 s with the 8-bit model
  (Ollama's 4-bit build was ~2–8 s); try the 4-bit MLX build in M2's model comparison
- [x] Rebuild the index (different runtime/quantization ⇒ different vectors)
- [x] Friendly CLI error when the model server is unreachable (instead of a traceback)
- [x] Update AGENTS.md tech stack, README, `.env.example`

**Done when:** the full test suite passes and `ingest` / `ask` work against the chosen runtime.

---

## M2 — Evaluation baseline 🟡

**Goal:** measure quality before optimizing, so later changes are comparable.
**Learning focus:** LangSmith tracing, datasets, evaluators.

- [x] Enable LangSmith tracing via env vars
- [x] Small golden dataset (12 Q&A pairs over a six-document sample corpus)
  - [x] Seed corpus and 3 cases with validated loading and offline tests
  - [x] Expand to 7 cases over indexing, backup, and privacy documents, including
    a cross-source question and two unanswerable questions
  - [x] Expand to 12 validated cases across six source documents
  - [x] Include three unanswerable questions, French answer and refusal cases,
    and two questions requiring multiple sources
- [ ] Retrieval check (is the expected source retrieved?) and answer check (LLM-as-judge or reference match)
  - [x] Standalone batch prototype saves all 12 cases as JSONL with retrieved
    sources/distances, answers, citations, and separate retrieval/generation timings
  - [x] Extract dependency-injected `run_eval_case` with typed result records;
    verify single retrieval, reference isolation, citations, timing boundaries,
    and empty-context behavior offline (44 tests passing overall)
  - [x] Standalone source-recall scoring reads saved JSONL, checks result IDs and
    question alignment, and excludes unanswerable cases from the mean
  - [x] Extract and test reusable source-recall calculation: full/partial/zero
    recall, duplicate sources, and N/A for empty expectations (52 tests overall)
  - [x] Define manual answer-review criteria: correctness, completeness, and
    citation support; calibrate on `cross-source-002` and `privacy-002`
  - [x] Persist two manual reviews for the first batch and verify their answer
    and citation snapshots against the original result rows
  - [x] Verify standalone review validation rejects an altered answer snapshot
    and passes again after restoring the original text
  - [x] Add strict review models and reusable `load_reviews` with ten offline
    tests for snapshots, field types, duplicate reviews, and run association
    (62 tests passing overall)
  - [x] Complete all twelve rubric-based reviews and summarize answer-quality scores
    - [x] Verify standalone summary distinguishes review coverage (2/12, 16.7%)
      from reviewed-subset pass rates and withholds the full-dataset pass rate
    - [x] Extract pure `summarize_reviews` and typed `ReviewSummary`; verify
      partial/full coverage and each failed criterion (67 tests overall)
  - [x] Manual smoke check in isolated `storage/eval-smoke`: all four added cases
    (backup recovery, privacy, cross-source answer, unsupported encryption)
    behaved as expected, including citations and refusal behavior
  - [x] Re-ingest six documents (six chunks) and smoke-test `cross-source-002`:
    both expected sources were cited, but the answer contradicted itself
  - [x] Confirm `privacy-002`: complete French refusal without citations;
    the documents do not specify external diagnostic data retention
- [ ] Record baseline scores in this file
  - [x] Verify standalone SHA-256 fingerprints for raw case-file bytes and a
    sorted mapping of corpus-relative paths to supported-file content hashes
  - [x] Extract typed `EvalFingerprints` and reusable `fingerprint_eval_data`;
    verify unchanged data, case formatting, document content, renaming, ignored
    files, corpus relocation, and empty-corpus rejection (74 tests overall)
  - [ ] Capture run settings and bind fingerprints to index construction
    - [x] Verify offline configuration preview with explicit model-variant label,
      selected non-secret parameters, data fingerprints, and installed versions
    - [x] Add strict `RunParameters` and ten offline cases for JSON round trips,
      invalid parameter values/types, and unexpected secret fields (84 tests overall)
    - [ ] Use recorded parameters for execution and build a fresh associated index
- [x] Measure latency (retrieve / generate) alongside quality
- [ ] Compare chat models on the same set: Qwen3.5-9B MLX 8-bit (current) vs 4-bit

**Done when:** one command runs the eval and baseline numbers are recorded.

**Preliminary batch observations (not the final reproducible baseline):**

Run: `20261028T131020882835Z.jsonl`; full reviews:
`20261028T131020882835Z.complete.reviews.json` under local `storage/eval-results/`.
The original two-review example is retained separately. Review coverage is 12/12;
correctness, completeness, citation behavior, and all-criteria pass counts are each
12/12. Mean source recall over nine answerable cases is 100%; the three unanswerable
cases are excluded from that metric. The assistant inspected the saved answers
against rubric v1 and the corpus, including the ten newly recorded judgments;
these scores are not independent human ratings or a separately calibrated judge.
This single small-corpus run does not erase the earlier contradictory smoke answer.
Run configuration/corpus version capture and a unified evaluation command remain
pending before declaring the formal baseline.

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
- [ ] Embedding model comparison (`qwen3-embedding` 0.6b vs 4b vs 8b: quality vs indexing time)
- [ ] Qwen3-Embedding query instruction prefix (`Instruct: ...\nQuery:` on queries only); a
  5-note spot check on 2026-10-07 showed no clear gain, so measure on the M2 eval set first
- [ ] Calibrate `retrieval_max_distance` from eval data (off by default in M1)
- [ ] Structured answer output (`found` flag + text) so a not-found answer can never carry
  citations, instead of relying on the model to follow the prompt
- [ ] Multi-granularity (parent-document) retrieval: match small chunks, give the LLM their
  enclosing Markdown section; pairs naturally with header-aware splitting
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
- Optional cloud provider (OpenAI / GitHub Models) selectable via config
- Watch a folder and auto-ingest changes
- Show sources as paths relative to the data directory
- User feedback on answers (e.g. `ask` prompts y/n, logged locally) to grow the eval set

---

## Changelog

- **2026-10-28** — Added strict `RunParameters` and switched configuration preview
  to serialize this explicit non-secret parameter model. Ten new offline test
  cases cover JSON round trips with/without a distance threshold, invalid ranges,
  strict integer typing, chunk overlap, blank variant labels, and unexpected API
  key fields (84 tests passing). The batch runner still needs to consume these
  parameters and construct an associated fresh evaluation index.

- **2026-10-28** — Verified offline configuration preview for the current MLX
  8-bit label, selected chat/embedding/chunk parameters, effective prototype
  retrieval settings (k=4, no distance threshold), data fingerprints, Python,
  and installed package versions. The label is user-supplied rather than server
  detected. This preview is not a historical run record; shared execution
  parameters, index association, and persisted run metadata remain pending.

- **2026-10-28** — Extracted typed evaluation data fingerprints and added seven
  offline tests. Fingerprints detect case-byte, document-content, and relative
  filename changes while ignoring unsupported/hidden files and absolute corpus
  location. Empty supported corpora are rejected (74 tests passing; Ruff passed).
  Run-settings capture and association with index construction remain pending.

- **2026-10-28** — Verified the standalone data-fingerprint prototype against
  the current twelve-case, six-document dataset. Case fingerprints cover raw
  bytes; corpus fingerprints cover relative filenames and file hashes with
  deterministic key ordering. Current fingerprints are not retroactive evidence
  of the data or index used by the earlier run. Module extraction, tests, and
  integration with run configuration/index provenance remain pending.

- **2026-10-28** — Completed rubric-v1 reviews for all twelve saved batch answers.
  Added ten assistant-reviewed decisions with source-based reasons and exact
  answer/citation snapshots to a new full-review file, retaining the two-review
  example. Existing validation and summary scripts confirm 12/12 coverage and
  12/12 passes for each criterion and the all-criteria check. Recorded these as
  preliminary assistant-reviewed observations rather than independent ratings
  or the final reproducible baseline.

- **2026-10-28** — Extracted pure `summarize_reviews` and typed review-summary
  counts; the standalone summary script retains result/dataset matching and
  display. Five new offline test cases verify partial/full coverage and that
  each individual failed criterion prevents an all-criteria pass (67 tests
  passing; Ruff passed). Structured manual review coverage remains 2/12; no
  full-dataset answer-quality score has been declared.

- **2026-10-28** — Verified the standalone manual-review summary: coverage is
  2/12 (16.7%); each criterion and the all-criteria check pass for both reviewed
  answers. Full-dataset answer pass rate remains N/A, with ten pending IDs listed.
  Reusable summary extraction and tests remain pending.

- **2026-10-28** — Added strict `AnswerReview`/`ReviewFile` models and reusable
  `load_reviews`; the validation script now delegates to the module. Added ten
  offline tests covering preserved snapshot whitespace, invalid judgment fields,
  unknown IDs, changed answers/citations, duplicate reviews, and wrong run files
  (62 tests passing; Ruff passed). Two of twelve answers have structured manual
  reviews; full review coverage and answer-score aggregation remain pending.

- **2026-10-28** — Saved two structured manual reviews for batch
  `20261028T131020882835Z`, with rubric version, answer/citation snapshots, three
  boolean judgments, and reasons. Verified both snapshots against the twelve-row
  result file; review coverage is 2/12, not a full-dataset answer score. Reusable
  validation and tests remain pending.

- **2026-10-28** — Defined separate manual answer criteria for correctness,
  completeness, and citation support. Concise answers need not repeat the
  reference verbatim or cite every expected retrieval source. Under this rubric,
  the saved batch's concise `cross-source-002` answer and French `privacy-002`
  refusal both pass all three checks. This does not change the earlier smoke
  answer's contradiction failure. Structured review persistence remains pending.

- **2026-10-28** — Extracted the pure `source_recall` metric and added eight
  parameterized offline tests. Source sets prevent duplicate passages from
  inflating recall; empty expectations return None and are excluded from the
  mean. The scorer still reports 100% mean source recall for the nine answerable
  cases in the saved batch (52 tests passing; Ruff passed). Automated answer
  quality checks and run configuration capture remain pending.

- **2026-10-28** — Verified the standalone source-recall scorer on the first
  saved batch: nine answerable cases scored 100% mean source recall; three
  unanswerable cases were reported as N/A and excluded. Result matching rejects
  duplicate IDs, missing/extra IDs, and changed question text. Reusable metric
  extraction and tests remain pending; this metric does not assess answer quality.

- **2026-10-28** — Extracted `run_eval_case` into `evaluation.py`, receiving its
  vector store, chat model, corpus path, and retrieval parameters explicitly.
  The batch script retains configuration and incremental JSONL output. Added
  two offline tests for result recording, a single retrieval call, reference
  isolation from prompts, deterministic timing boundaries, and skipping the
  model when retrieval is empty (44 tests passing; Ruff passed). The first batch
  recorded mean retrieval/generation times of 1.447/13.703 seconds; these include
  request overhead and any model loading, without a controlled warm-up protocol.
  Automated scoring and run configuration capture remain pending.

- **2026-10-28** — Completed the first twelve-case batch run with the standalone
  prototype (`20261028T131020882835Z.jsonl`, under ignored `storage/eval-results`).
  All nine answerable cases retrieved every expected source at top-k four
  (mean source recall 100%); all three unanswerable cases refused without citations
  on manual inspection. `cross-source-002` no longer contradicted itself, but
  only explicitly stated and cited the backup side of the comparison. These are
  preliminary observations; automated scoring, run configuration capture, and
  reusable runner tests remain pending before declaring a formal baseline.

- **2026-10-28** — Smoke-tested the expanded six-document index with top-k four.
  `cross-source-002` cited both expected sources but incorrectly opened by saying
  conversation exports contain original files, contradicting its later correct
  explanation and conclusion. Treat this answer as a manual quality failure.
  The complete `privacy-002` output correctly stated in French that the context
  does not specify external diagnostic data retention, without citations; it
  passed manual inspection. Preserve these
  observations for baseline evaluation before changing prompts or model settings.

- **2026-10-28** — Completed the initial golden dataset: twelve validated cases
  over six documents, adding import, search, and export topics. Includes nine
  answerable cases, three unanswerable cases, two cross-source questions, and
  French answer/refusal coverage. The five newest cases have not been run through
  RAG yet; automated scoring and baseline measurements remain pending.

- **2026-10-28** — Manually smoke-tested RAG using an isolated evaluation index
  (three documents, three chunks). The backup answer included both required facts
  and cited `backups.md`; the unsupported encryption question received a refusal
  without citations. The privacy answer correctly described external transmission
  and cited `privacy.md`; the cross-source answer covered both facts and cited
  `indexing.md` and `backups.md`. All four added cases passed manual inspection.
  These observations are not a scored evaluation baseline.

- **2026-10-28** — Expanded the evaluation seed to seven validated cases across
  three documents. Added backup and privacy topics, a two-source question, and
  an unanswerable backup-encryption question. Further corpus expansion is needed
  to measure source selection with the default top-k of four.

- **2026-10-28** — Added a seed evaluation corpus and three reference cases.
  Added typed dataset loading, source validation, and eight offline tests
  (42 tests passing overall). The dataset still needs expansion before baseline evaluation.

- **2026-10-28** — Enabled LangSmith tracing for the CLI using agent-based
  workspace configuration. Required `langsmith>=0.14.9` and
  `langchain-core>=1.6.11`; disabled tracing during tests to keep them offline.
  Verified the standalone smoke script and a real CLI answer trace.

- **2026-10-09** — Desktop apps (LM Studio, Bionic) removed; models now served by the headless
  `llmster` daemon (`lms daemon up` + `lms server start`). Pitfall found: after the apps were
  removed the hub model definition was gone, so the chat model appeared as `qwen3.5-9b-mlx`
  with no reasoning config — `reasoning_effort` was silently ignored (1,190 thinking tokens,
  ~211 s per answer). `lms get qwen/qwen3.5-9b --mlx` restored it (171 KB, no re-download).

- **2026-10-09** — Model runtime switched from Ollama to LM Studio's engine (Bionic and
  LM Studio share `~/.lmstudio`; `lms server start` launches whichever app ran last). Models:
  `qwen/qwen3.5-9b` (MLX 8-bit) and `text-embedding-qwen3-embedding-0.6b` (GGUF Q8).

- **2026-10-09** — M1 completed: `archivist ingest` / `ask` work end to end on local
  Ollama models. Known limitations recorded under M1 and scheduled into M1.5, M5 and Backlog.

- **2026-10-08** — Decided to replace Ollama after M1 (attribution, closed-source GUI, cloud
  pivot, proprietary model store); added M1.5 to evaluate OpenAI-compatible local runtimes.
  Added multi-granularity retrieval to M5; user feedback on answers moved to Backlog.

- **2026-10-05** — M0 completed: Typer CLI (`archivist config`), ruff/pytest config, 5 passing tests.

- **2026-10-05** — Default models chosen: chat `qwen3.5:9b-mlx` (fast on Apple Silicon via MLX,
  supports tools for M4), embeddings `qwen3-embedding:0.6b` (fast re-indexing during experiments).
  Compare against larger embedding variants (4b / 8b) once the M2 eval exists.

- **2026-10-05** — Switched LLM and embeddings from OpenAI to local **Ollama** (`langchain-ollama`)
  to avoid paid APIs. Cloud providers moved to backlog as an optional, config-selectable backend.

- **2026-10-05** — Default branch is `master` (not `main`); AGENTS.md git workflow updated.
  Remaining M0 work continues on `chore/project-scaffolding`. OpenAI API not yet funded —
  not needed for M0; M1 will keep loading/splitting and tests offline (fake embeddings) until it is.

- **2026-10-05** — M0 started. Chose `pydantic-settings` for configuration; M0 deps limited to
  `typer`, `pydantic-settings` (runtime) and `pytest`, `ruff` (dev). LangChain deps deferred to M1.

- **2026-10-05** — Initial roadmap: milestones M0–M6 and backlog defined. Decisions: OpenAI for LLM
  and embeddings, Chroma as vector store, CLI first then Streamlit, docs in English.
