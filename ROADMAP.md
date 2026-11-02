# Roadmap

Living plan for **Archivist**. Requirements and conventions live in [AGENTS.md](AGENTS.md).
Update this file whenever the plan changes, and add an entry to the [Changelog](#changelog).

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done · ⏸️ Deferred

| Milestone | Title                          | Status | Branch                         |
|-----------|--------------------------------|--------|--------------------------------|
| M0        | Project scaffolding            | ✅     | `chore/project-scaffolding`    |
| M1        | Minimal RAG pipeline (MD/TXT)  | ✅     | `feat/minimal-rag-pipeline`    |
| M1.5      | Local model runtime evaluation | ✅     | `refactor/openai-compatible-llm-provider` |
| M2        | Evaluation baseline            | ✅     | `feat/eval-baseline`           |
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

## M2 — Evaluation baseline ✅

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
- [x] Retrieval check (is the expected source retrieved?) and answer check (LLM-as-judge or reference match)
  - [x] Verify standalone local reference judge on saved `indexing-001`: valid
    structured output and a matching-reference verdict for the correct SHA-256 answer
  - [x] Check the reference judge rejects a SHA-256 answer with an appended
    contradictory MD5 claim, explaining the contradiction
  - [x] Extract `ReferenceGrade`, reference-judge prompt, and dependency-injected
    `grade_reference`; add six offline cases for payload/verdict handling, request
    failure propagation, and strict output fields (104 tests overall)
  - [x] Verify standalone batch reference grading with judge provenance and coverage:
    12/12 graded, 12/12 reference matches for the recorded run
  - [x] Extract typed `ReferenceGradeRecord` and lazy `iter_reference_grades`;
    six new offline cases cover ordered snapshots, false verdicts, partial failure,
    and invalid case/answer IDs (110 tests overall)
  - [x] Add three offline script cases for persisted true/false grades, provenance,
    unchanged answers, and failures before/after the first grade (113 tests overall)
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
- [x] Record baseline scores in this file
  - [x] Verify standalone SHA-256 fingerprints for raw case-file bytes and a
    sorted mapping of corpus-relative paths to supported-file content hashes
  - [x] Extract typed `EvalFingerprints` and reusable `fingerprint_eval_data`;
    verify unchanged data, case formatting, document content, renaming, ignored
    files, corpus relocation, and empty-corpus rejection (74 tests overall)
  - [x] Capture run settings and bind fingerprints to index construction
    - [x] Verify offline configuration preview with explicit model-variant label,
      selected non-secret parameters, data fingerprints, and installed versions
    - [x] Add strict `RunParameters` and ten offline cases for JSON round trips,
      invalid parameter values/types, and unexpected secret fields (84 tests overall)
    - [x] Prepare an isolated run with copied input files, matching fingerprints,
      recorded parameters/software, and a fresh six-chunk index; verify indexed status
    - [x] Run all twelve cases from the prepared manifest using its recorded
      parameters; confirm completed status, matching IDs/questions and snapshot hashes
    - [x] Extract `load_indexed_run` and add eleven offline preflight tests:
      eligible state/schema, snapshot matching, index presence, software versions,
      and existing-result protection (95 tests overall)
    - [x] Add three offline workflow tests with real local Chroma and fake models:
      snapshot/recorded-parameter isolation, partial-result preservation on generation
      failure, and no indexed status on preparation failure (98 tests overall)
- [x] Verify standalone report binds completed generation/grading, input hashes,
  answer/reference snapshots, IDs, counts, and finite non-negative timings
- [x] Extract `build_eval_report` and add thirteen offline cases for metric
  denominators/means, mismatched metadata, changed snapshots, missing grades,
  and invalid timings (126 tests overall)
- [x] Provide one command for preparation, execution, grading, and reporting
  - [x] Verify `scripts/eval_all.py` creates a fresh run and saves validated `report.json`
  - [x] Add two offline unified-entry tests for separate candidate/judge models,
    saved reports, stop-on-failure, and restored environment/argv (128 tests overall)
- [x] Measure latency (retrieve / generate) alongside quality
- [x] Compare chat models on the same set: Qwen3.5-9B MLX 8-bit (current) vs 4-bit
  - [x] Verify both local MLX weight directories report 4/8 quantization bits
  - [x] Inspect service: on 2026-11-01 the unqualified hub key resolved to and
    had loaded 4-bit; selecting an already downloaded 8-bit option via `lms get`
    did not change its default on 2026-11-02
  - [x] Add local single-base definitions `archivist/qwen35-4bit` and
    `archivist/qwen35-8bit`; verify service quantization metadata and reasoning controls
  - [x] Load and verify `archivist/qwen35-8bit`: 8-bit weights and parallelism 1;
    requested context 8192 was reported as 50432 (saved local load-profile snapshot)
  - [x] Complete verified 8-bit control `20261102T104331523050Z` with the fixed
    8-bit judge; attach before/after loaded-model observations and validate report
  - [x] Load verified 4-bit/parallel 1 (reported context 92672, requested 8192)
    and prepare `20261102T105018572021Z`; dataset and non-model parameters match
    the 8-bit control, with the preflight model observation attached
  - [x] Generate all twelve 4-bit answers and verify unchanged snapshots and
    post-generation 4-bit/parallel 1/context 92672
  - [x] Rerun both verified aliases with a fixed verified judge, parallelism 1,
    matching requested context and recorded actual load profiles. Treat differences
    as practical runtime observations when MLX auto-fit prevents equal effective context.

- [x] Document evaluation commands, artifacts, model provenance, and comparison limits
- [x] Final checks: 128 tests, Ruff lint/format, and 12-case dataset validation

**Done when:** one command runs the eval and baseline numbers are recorded.

**Verified quantization comparison (2026-11-02):**

| Metric | MLX 8-bit | MLX 4-bit |
|--------|-----------|-----------|
| Candidate model | `archivist/qwen35-8bit` | `archivist/qwen35-4bit` |
| Run | `20261102T104331523050Z` | `20261102T105018572021Z` |
| Grading batch | `20261102T104456095520Z` | `20261102T105639547639Z` |
| Mean source recall (9 answerable cases) | 100% | 100% |
| Reference matches (same 8-bit judge) | 12/12 | 12/12 |
| Mean retrieval time | 0.228 s | 0.171 s |
| Mean generation time | 5.187 s | 3.788 s |
| Requested context / parallelism | 8192 / 1 | 8192 / 1 |
| Observed candidate context / parallelism | 50432 / 1 | 92672 / 1 |

Both use the same dataset fingerprints, non-model generation/retrieval parameters,
and `reference-v1` rubric. Both saved reports pass offline provenance/snapshot
validation. Loaded-model observations confirm each candidate's quantization;
`judge-models-before.json` in the 4-bit run confirms the fixed 8-bit judge at
context 50432 and parallelism 1. Artifacts remain in local `storage/eval-runs/`.

The 4-bit run's mean generation time was about 27.0% lower in this experiment.
These are single runs without controlled warm-up; MLX auto-fit produced different
effective contexts. Treat timing differences as practical runtime observations,
not a quantization-only causal estimate. Matching judge verdicts on twelve cases
do not establish general quality equivalence or citation accuracy. Earlier
unqualified-model runs below remain historical observations with unverified
quantization.

**Recorded single-run results (quantization not independently verified):**

Answer run: `20261028T214751612403Z`; grading batch: `20261101T204407833512Z`.
Artifacts live under local `storage/eval-runs/`. The offline report validates their
association before calculating metrics.

Chat: `qwen/qwen3.5-9b`, user-labeled MLX 8-bit, temperature 0.2, thinking off.
The unqualified hub key is not a quantization pin: on 2026-11-01 its selected
and currently loaded variant was verified as 4-bit. Historical manifests preserve
the supplied 8-bit label, but do not prove which weights served those earlier
requests. Do not use these runs as a verified 8-bit control or relabel them as
4-bit without historical evidence; rerun both variants with verified selection.
Embeddings: `text-embedding-qwen3-embedding-0.6b`. Chunk size/overlap: 1000/200;
retrieval k=4 with no distance threshold. Judge: the same model/variant at
temperature 0, thinking off, using rubric `reference-v1`.

| Metric | Result |
|--------|--------|
| Corpus / cases | 6 documents / 12 questions |
| Mean source recall | 100% across 9 answerable cases |
| Reference-grade coverage | 12/12 |
| Reference matches | 12/12 (100%) |
| Mean retrieval time | 1.310 s |
| Mean generation time | 13.865 s |

Case-file SHA-256: `121ef4e82882deceb33130cf88cf68f5cfe318a308b6d9f6ab24cd243524580d`.
Corpus SHA-256: `ef021c03839850ce5eec2bbcaf0be714b18d63518895643bff3734f94a588f5f`.

These are single-run measurements without controlled warm-up; timings include
request overhead. Reference matching is a local-model judgment, not independently
verified factual accuracy, and citation accuracy is not automatically scored.
The three unanswerable cases are excluded from source recall but included in
reference grading. Report module/tests and one-command execution are verified;
unified-entry regression tests also pass. The verified 4-bit/8-bit comparison is complete; documentation
closeout is complete. M2 is done with 128 offline tests passing.

**Unified-command confirmation run:** `20261101T223119480432Z`, grading batch
`20261101T223350953139Z`, with the same recorded data fingerprints, 8-bit model
labels, and parameters. Source recall is 100% across nine answerable cases;
reference matches are 12/12. Mean retrieval/generation times are 1.418/9.617 s.
The saved `report.json` matches a fresh offline recomputation. These uncontrolled
single-run timing differences do not establish an SSD or other causal speedup.

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
This earlier batch lacked the run configuration/snapshot capture used by the
recorded baseline above. Its reviews remain separate from the newer run.

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

- **2026-11-02** — Close M2 after verified model comparison and documentation
  review. README now documents unified/staged evaluation, saved artifacts,
  offline reporting, local alias setup requirements, and metric limitations.
  AGENTS records the evaluation module/script boundary and avoids assuming an
  unqualified model name pins 8-bit weights. Final checks: 128 tests passing,
  Ruff lint and format checks passing, and all twelve evaluation cases valid.

- **2026-11-02** — Completed the verified 4-bit/8-bit comparison using the same
  8-bit reference judge. Validated and saved the 4-bit run report with grading
  batch `20261102T105639547639Z`: 12/12 matches and 100% mean source recall over
  nine answerable cases. Recorded 3.788 s versus 5.187 s mean generation time,
  differing observed contexts, and single-run/judge limitations. Documentation
  closeout remains before M2 completion.

- **2026-11-02** — Verified all twelve answers in 4-bit candidate run
  `20261102T105018572021Z`: IDs/questions and snapshot hashes match. Attached
  post-generation model observation confirming 4-bit/parallel 1/context 92672.
  Mean source recall is 100% over nine answerable cases; observed mean retrieval
  and generation times are 0.171/3.788 s. Reference quality has not yet been graded
  for this run; next switch to the same verified 8-bit judge used for the control.

- **2026-11-02** — Verified `archivist/qwen35-4bit` is loaded at 4-bit/parallel 1
  after unloading the 8-bit model. MLX reports context 92672 despite the same 8192
  request, versus 50432 for the 8-bit control. Prepared isolated run
  `20261102T105018572021Z` (six documents/chunks, twelve cases), attached its
  original preflight observation, and confirmed identical dataset fingerprints
  and parameters except candidate model/variant. Answer generation is pending;
  grade later with the same verified 8-bit judge, using sequential model residency.

- **2026-11-02** — Completed verified 8-bit control run `20261102T104331523050Z`
  using `archivist/qwen35-8bit` for both candidate and judge. Recomputed report
  matches: source recall 100%, reference matches 12/12, mean retrieval 0.228 s,
  mean generation 5.187 s. Input fingerprints are unchanged. Attached original
  preflight and post-run model observations confirming 8-bit/parallel 1/context
  50432; requested context was 8192. The 4-bit candidate and fixed 8-bit judge
  comparison remains pending; avoid simultaneous large-model residency when
  collecting the next run's timings.

- **2026-11-02** — Verified the explicitly loaded 8-bit alias and parallelism 1.
  The request specified context 8192 but `lms ps` reports 50432. Original copied
  model definitions contain no load-time context override. This is consistent
  with upstream MLX auto-fit issues #366/#2318, though the precise local cause
  has not been independently isolated. Saved the observed load profile under
  local `storage/model-profiles/`. Continue the same-dataset application comparison
  with requested and actual context recorded; do not claim a strictly controlled
  quantization-only timing effect when actual contexts differ. No runtime update
  or new model load was performed during this check.

- **2026-11-02** — Confirmed `lms get --select` did not switch the unqualified
  model's selected variant; no models were loaded at inspection time. The native
  load API also rejected the full indexed variant key. Added two new local model
  definitions under `~/.lmstudio/hub/models/archivist/`, each binding exactly one
  existing MLX weight repo, with original operation/customFields preserved.
  `lms ls` and the native models API identify `archivist/qwen35-4bit` as 4-bit and
  `archivist/qwen35-8bit` as 8-bit, both retaining reasoning off/on capability.
  No weight files were copied/downloaded or original definitions changed. The
  8-bit alias resolves in CLI estimation at context 8192/parallel 1 (13.63 GiB,
  low-confidence estimate); actual loading verification and comparison runs remain
  pending. Keep the local definition files for reproducing these API model IDs.

- **2026-11-01** — Audited installed weights and live model identity before the
  quantization comparison. Both Qwen3.5-9B MLX builds are present on the accessible
  external SSD; their config files report 4/8 bits. `lms ls --variants --json`
  and `lms ps --json` show the unqualified hub key currently selects/loads 4-bit.
  Earlier runs used that unqualified key plus hand-entered 8-bit labels, so their
  historical quantization is unverified; artifacts are retained unchanged.
  The installed CLI also rejected an @8bit key in a non-loading estimate command,
  matching upstream lms issue #588. Verified variant selection and fresh comparison
  runs are required. No models were downloaded, loaded, or unloaded during this audit.

- **2026-11-01** — Added two offline unified-entry tests with real temporary
  Chroma and fake models. Verified distinct candidate/judge IDs and temperatures,
  saved complete reports, restoration of prior environment/argv on success, and
  stopping before report generation when grading fails. Failure preserves the
  completed answer run and incomplete grading record, and removes temporary model
  overrides when no prior value existed (128 tests passing). M2 now awaits the
  4-bit comparison and final documentation closeout.

- **2026-11-01** — Verified the unified evaluation entry on a new real-model run
  `20261101T223119480432Z`. Preparation, twelve answers, twelve reference grades,
  and saved report completed in order. Report recomputation matches the saved
  artifact: source recall 100%, reference matches 12/12, mean retrieval 1.418 s,
  mean generation 9.617 s. Candidate/judge model selection is explicit; unified
  entry regression tests and the controlled 4-bit comparison remain pending.

- **2026-11-01** — Extracted `build_eval_report`; the report script now handles
  arguments and JSON display only. Thirteen offline cases verify partial source
  recall, unanswerable-case exclusion, reference-match denominators, mean timings,
  rejected incomplete/mixed/hash-mismatched/count-mismatched metadata, changed
  inputs/answer snapshots, missing grades, and invalid timing values (126 tests
  passing). The recorded 8-bit report remains unchanged.

- **2026-11-01** — Verified the standalone unified report and recorded the 8-bit
  single-run baseline: nine-case mean source recall 100%, twelve-case reference
  match rate 100%, mean retrieval 1.310 s, and mean generation 13.865 s. The report
  checks completed states, run identity, hashes, per-case snapshots, coverage/counts,
  and finite non-negative timings. No new model calls were needed. Report module
  extraction/tests, one-command orchestration, and 4-bit comparison remain pending.

- **2026-11-01** — Added three offline batch-judge script cases verifying saved
  true/false grades, source-run/result/input/prompt provenance, judge configuration,
  output schema, secret exclusion, and unchanged original answers. Failures on the
  first or second request preserve the actual completed rows, mark the batch
  incomplete, and do not fabricate failed grades (113 tests passing).

- **2026-11-01** — Extracted typed per-case reference-grade records and a lazy,
  dependency-injected batch grading iterator. The script retains incremental
  writes, progress counts, and metadata updates. Six new offline cases verify
  input-to-record mapping independent of answer-dictionary order, preserved false
  verdicts, deferred model calls, exception propagation after a yielded record,
  and rejected empty/duplicate/mismatched IDs (110 tests passing). Actual script
  persistence and provenance/failure-count regression coverage remain pending.

- **2026-11-01** — Completed standalone batch reference grading of recorded run
  `20261028T214751612403Z`; grading batch `20261101T204407833512Z` contains twelve
  grades, all reference matches. Verified saved answer/reference snapshots, IDs,
  questions, result-file hash, input fingerprints, metadata counts, and completed
  status. Judge: Qwen3.5-9B, user-labeled MLX 8-bit, temperature 0, thinking off.
  Spot-checked the cross-source comparison and French refusal reasons. A prior
  connection-refused attempt was preserved as incomplete with 0/12 grades. The
  100% figure is this judge's reference-match rate, not independently verified
  factual/citation accuracy. Reusable batch implementation/tests remain pending.

- **2026-10-31** — Extracted `ReferenceGrade`, `REFERENCE_JUDGE_PROMPT`, and
  dependency-injected `grade_reference`; the smoke script retains input selection,
  model configuration, and display. Six offline cases verify structured-output
  setup, payload contents, preservation of true/false verdicts, propagation of
  judge failures, and invalid output fields (104 tests passing). These tests
  verify code behavior; semantic judge calibration remains limited to the two
  previously observed real-model examples. Batch grading/provenance is pending.

- **2026-10-31** — Calibrated the standalone reference judge with one deliberately
  contradictory candidate: the saved SHA-256 answer plus an MD5 claim. It returned
  false and identified the conflict. Together with the correct-answer smoke check,
  this verifies two examples, not general judge accuracy. Restore the unmodified
  candidate input before reusable judge extraction and offline tests.

- **2026-10-31** — Verified the standalone local reference judge on recorded run
  `20261028T214751612403Z`, case `indexing-001`: JSON-schema output parsed and
  correctly accepted the SHA-256 answer. An initial connection-refused error was
  resolved by starting the local model service. Negative-case calibration and
  reusable judge implementation/tests remain pending. The owner reports moving
  model files to an external SSD, with the original local model directory linked
  to the corresponding SSD directory; the local API remains the integration point.

- **2026-10-30** — Added three offline script-workflow tests using temporary
  directories, real persistent Chroma, and fake embedding/chat dependencies.
  Verified successful preparation/execution uses copied inputs and recorded model
  parameters despite changes to the originals/current settings. Verified generation
  failure preserves earlier rows without completed status, and embedding setup
  failure leaves prepared status without results (98 tests passing).

- **2026-10-30** — Extracted `load_indexed_run` with explicitly supplied current
  software versions and removed duplicate checks from the execution script.
  Added eleven offline cases for matching runs, rejected states/schema, modified
  case/document snapshots, missing index files, changed Python/package versions,
  and preserving existing results (95 tests passing). These tests cover preflight
  validation using an index-file placeholder, not Chroma contents or the complete
  preparation/execution lifecycle.

- **2026-10-29** — Verified recorded run `20261028T214751612403Z` completed all
  twelve cases using its prepared snapshot/index. Result IDs and questions match
  the snapshot; fingerprints remain unchanged. All nine answerable cases have
  full source recall (mean 100%). Answer-quality reviews for this newly generated
  batch are still pending and cannot be inherited from the earlier run. Dedicated
  preparation/execution guard tests remain pending.

- **2026-10-28** — Prepared run `20261028T214751612403Z` with a copied twelve-case,
  six-document input snapshot, manifest, and fresh six-chunk Chroma index. Checked
  indexed status, snapshot hashes, case count, and index presence. Generation from
  this recorded run is pending; the old batch and its reviews remain separate.

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
