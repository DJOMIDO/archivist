"""Prepare a recorded evaluation run and build its isolated index."""

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from platform import python_version
from shutil import copyfile

from dotenv import load_dotenv
from langchain_core.tracers.langchain import wait_for_all_tracers

from archivist.config import Settings
from archivist.evaluation import (
    RunParameters,
    fingerprint_eval_data,
    load_eval_cases,
)
from archivist.indexing import get_embeddings, get_vector_store
from archivist.loaders import find_files
from archivist.pipeline import ingest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--chat-variant", required=True)
args = parser.parse_args()

load_dotenv(dotenv_path=".env")
settings = Settings()
parameters = RunParameters(
    chat_variant=args.chat_variant,
    chat_model=settings.chat_model,
    chat_temperature=settings.chat_temperature,
    chat_reasoning_effort=settings.chat_reasoning_effort,
    embedding_model=settings.embedding_model,
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    k=4,
    max_distance=None,
)

run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
run_dir = Path("storage/eval-runs") / run_id
run_dir.mkdir(parents=True)

corpus = run_dir / "inputs/corpus"
corpus.mkdir(parents=True)
cases_path = run_dir / "inputs/cases.json"
copyfile("evals/cases.json", cases_path)

source = Path("evals/corpus")
for path in find_files(source):
    target = corpus / path.relative_to(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    copyfile(path, target)

cases = load_eval_cases(cases_path, corpus)
fingerprints = fingerprint_eval_data(cases_path, corpus)

record = {
    "schema_version": 1,
    "run_id": run_id,
    "status": "prepared",
    "parameters": parameters.model_dump(mode="json"),
    "data": asdict(fingerprints),
    "paths": {
        "cases": "inputs/cases.json",
        "corpus": "inputs/corpus",
        "index": "chroma",
    },
    "software": {
        "python": python_version(),
        "packages": {
            package: version(package)
            for package in (
                "langchain-core",
                "langchain-openai",
                "langchain-chroma",
                "langchain-text-splitters",
                "langsmith",
                "chromadb",
            )
        },
    },
}
manifest = run_dir / "manifest.json"
with manifest.open("x", encoding="utf-8") as file:
    file.write(json.dumps(record, indent=2, ensure_ascii=False) + "\n")

try:
    embeddings = get_embeddings(
        parameters.embedding_model,
        settings.llm_base_url,
        settings.llm_api_key,
    )
    store = get_vector_store(embeddings, run_dir / "chroma")
    result = ingest(
        corpus,
        store,
        chunk_size=parameters.chunk_size,
        chunk_overlap=parameters.chunk_overlap,
    )
    if fingerprint_eval_data(cases_path, corpus) != fingerprints:
        raise ValueError("Input snapshot changed during indexing")

    record.update(
        status="indexed",
        documents=result.documents,
        chunks=result.chunks,
        cases=len(cases),
    )
    manifest.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
finally:
    wait_for_all_tracers()

print(f"Indexed {result.documents} documents ({result.chunks} chunks).")
print(f"Prepared run: {run_dir}")
