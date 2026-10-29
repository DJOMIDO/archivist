"""Run evaluation using a prepared manifest, snapshot, and index."""

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from platform import python_version

from dotenv import load_dotenv
from langchain_core.tracers.langchain import wait_for_all_tracers

from archivist.config import Settings
from archivist.evaluation import (
    RunParameters,
    fingerprint_eval_data,
    load_eval_cases,
    run_eval_case,
)
from archivist.indexing import get_embeddings, get_vector_store
from archivist.qa import SYSTEM_PROMPT, get_chat_model

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run_dir", type=Path)
args = parser.parse_args()

load_dotenv(dotenv_path=".env")
settings = Settings()
run_dir = args.run_dir
manifest = run_dir / "manifest.json"
record = json.loads(manifest.read_text(encoding="utf-8"))

if record["schema_version"] != 1 or record["status"] != "indexed":
    raise ValueError("Expected an indexed run with schema version 1")

parameters = RunParameters.model_validate(record["parameters"])
cases_path = run_dir / "inputs/cases.json"
corpus = run_dir / "inputs/corpus"

if asdict(fingerprint_eval_data(cases_path, corpus)) != record["data"]:
    raise ValueError("Input snapshot no longer matches the manifest")
if not (run_dir / "chroma/chroma.sqlite3").is_file():
    raise FileNotFoundError("Prepared index is missing")

software = record["software"]
if python_version() != software["python"] or any(
    version(name) != expected for name, expected in software["packages"].items()
):
    raise ValueError("Software versions changed; prepare a new run")

cases = load_eval_cases(cases_path, corpus)
output = run_dir / "results.jsonl"

try:
    with output.open("x", encoding="utf-8") as file:
        record.update(
            status="running",
            started_at=datetime.now(UTC).isoformat(),
            prompt_sha256=sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        )
        manifest.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        embeddings = get_embeddings(
            parameters.embedding_model,
            settings.llm_base_url,
            settings.llm_api_key,
        )
        store = get_vector_store(embeddings, run_dir / "chroma")
        if len(store.get(include=[])["ids"]) != record["chunks"]:
            raise ValueError("Index chunk count no longer matches the manifest")

        llm = get_chat_model(
            parameters.chat_model,
            settings.llm_base_url,
            settings.llm_api_key,
            parameters.chat_temperature,
            parameters.chat_reasoning_effort,
        )

        for case in cases:
            result = run_eval_case(
                case,
                vector_store=store,
                llm=llm,
                corpus_dir=corpus,
                k=parameters.k,
                max_distance=parameters.max_distance,
            )
            file.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
            file.flush()
            print(f"Completed {case.id}", flush=True)

        if asdict(fingerprint_eval_data(cases_path, corpus)) != record["data"]:
            raise ValueError("Input snapshot changed during evaluation")

    record.update(
        status="completed",
        completed_cases=len(cases),
        finished_at=datetime.now(UTC).isoformat(),
        results_file="results.jsonl",
    )
    manifest.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
finally:
    wait_for_all_tracers()

print(f"Saved results to {output}")
