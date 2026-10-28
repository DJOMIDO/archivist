"""Run evaluation cases and save raw results without scoring."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tracers.langchain import wait_for_all_tracers

from archivist.config import Settings
from archivist.evaluation import load_eval_cases, run_eval_case
from archivist.indexing import get_embeddings, get_vector_store
from archivist.qa import get_chat_model

load_dotenv(dotenv_path=".env")

corpus = Path("evals/corpus").resolve()
cases = load_eval_cases(Path("evals/cases.json"), corpus)
settings = Settings(storage_dir=Path("storage/eval-smoke"))

embeddings = get_embeddings(
    settings.embedding_model,
    settings.llm_base_url,
    settings.llm_api_key,
)
store = get_vector_store(embeddings, settings.storage_dir / "chroma")
llm = get_chat_model(
    settings.chat_model,
    settings.llm_base_url,
    settings.llm_api_key,
    settings.chat_temperature,
    settings.chat_reasoning_effort,
)

output_dir = Path("storage/eval-results")
output_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
output = output_dir / f"{stamp}.jsonl"

try:
    with output.open("x", encoding="utf-8") as file:
        for case in cases:
            result = run_eval_case(
                case,
                vector_store=store,
                llm=llm,
                corpus_dir=corpus,
                k=4,
                max_distance=None,
            )

            file.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
            file.flush()
            print(f"Completed {case.id}", flush=True)
finally:
    wait_for_all_tracers()

print(f"Saved results to {output}")
