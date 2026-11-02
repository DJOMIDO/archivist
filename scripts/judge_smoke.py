"""Judge reference consistency for one saved answer."""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tracers.langchain import wait_for_all_tracers

from archivist.config import Settings
from archivist.evaluation import grade_reference, load_eval_cases
from archivist.qa import get_chat_model

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run_dir", type=Path)
parser.add_argument("case_id")
args = parser.parse_args()

cases = load_eval_cases(
    args.run_dir / "inputs/cases.json",
    args.run_dir / "inputs/corpus",
)
rows = [
    json.loads(line)
    for line in (args.run_dir / "results.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
]
case = next(case for case in cases if case.id == args.case_id)
row = next(row for row in rows if row["id"] == args.case_id)
if row["question"] != case.question:
    raise ValueError("Question mismatch")

load_dotenv(dotenv_path=".env")
settings = Settings()
llm = get_chat_model(
    settings.chat_model,
    settings.llm_base_url,
    settings.llm_api_key,
    0.0,
    settings.chat_reasoning_effort,
)
try:
    grade = grade_reference(case, row["answer"], llm)
    print(grade.model_dump_json(indent=2))
finally:
    wait_for_all_tracers()
