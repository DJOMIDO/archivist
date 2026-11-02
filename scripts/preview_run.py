"""Preview evaluation configuration without running models."""

import argparse
import json
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from platform import python_version

from dotenv import load_dotenv

from archivist.config import Settings
from archivist.evaluation import RunParameters, fingerprint_eval_data

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

record = {
    "kind": "configuration-preview",
    "parameters": parameters.model_dump(mode="json"),
    "data": asdict(
        fingerprint_eval_data(
            Path("evals/cases.json"),
            Path("evals/corpus"),
        )
    ),
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

print(json.dumps(record, indent=2, ensure_ascii=False))
