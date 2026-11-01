"""Grade saved answers and preserve judge provenance and partial results."""

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
    REFERENCE_JUDGE_PROMPT,
    ReferenceGrade,
    fingerprint_eval_data,
    iter_reference_grades,
    load_eval_cases,
)
from archivist.qa import get_chat_model

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run_dir", type=Path)
parser.add_argument("--judge-variant", required=True)
args = parser.parse_args()

run_dir = args.run_dir
record = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
if record["status"] != "completed":
    raise ValueError("Expected a completed answer-generation run")

cases = load_eval_cases(
    run_dir / "inputs/cases.json",
    run_dir / "inputs/corpus",
)
fingerprints = fingerprint_eval_data(
    run_dir / "inputs/cases.json",
    run_dir / "inputs/corpus",
)
if asdict(fingerprints) != record["data"]:
    raise ValueError("Input snapshot no longer matches the manifest")

result_bytes = (run_dir / "results.jsonl").read_bytes()
rows = [json.loads(line) for line in result_bytes.decode("utf-8").splitlines()]
by_id = {}
for row in rows:
    if row["id"] in by_id:
        raise ValueError(f"Duplicate result ID: {row['id']}")
    by_id[row["id"]] = row

if set(by_id) != {case.id for case in cases}:
    raise ValueError("Result IDs do not match dataset IDs")
for case in cases:
    if by_id[case.id]["question"] != case.question:
        raise ValueError(f"Question mismatch: {case.id}")

load_dotenv(dotenv_path=".env")
settings = Settings()
judge_config = {
    "model": settings.chat_model,
    "variant": args.judge_variant,
    "temperature": 0.0,
    "reasoning_effort": settings.chat_reasoning_effort,
}

stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
grade_dir = run_dir / "reference-grades" / stamp
grade_dir.mkdir(parents=True)
output = grade_dir / "grades.jsonl"
metadata_path = grade_dir / "metadata.json"

metadata = {
    "schema_version": 1,
    "status": "running",
    "source_run_id": record["run_id"],
    "results_sha256": sha256(result_bytes).hexdigest(),
    "data": asdict(fingerprints),
    "judge": judge_config,
    "rubric_version": "reference-v1",
    "prompt": REFERENCE_JUDGE_PROMPT,
    "prompt_sha256": sha256(REFERENCE_JUDGE_PROMPT.encode("utf-8")).hexdigest(),
    "output_schema": ReferenceGrade.model_json_schema(),
    "software": {
        "python": python_version(),
        "packages": {
            name: version(name)
            for name in (
                "langchain-core",
                "langchain-openai",
                "pydantic",
            )
        },
    },
    "expected_cases": len(cases),
    "started_at": datetime.now(UTC).isoformat(),
}

with metadata_path.open("x", encoding="utf-8") as file:
    file.write(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

completed = 0
passed = 0

try:
    llm = get_chat_model(
        judge_config["model"],
        settings.llm_base_url,
        settings.llm_api_key,
        judge_config["temperature"],
        judge_config["reasoning_effort"],
    )
    with output.open("x", encoding="utf-8") as file:
        answers = {case_id: row["answer"] for case_id, row in by_id.items()}
        for graded_row in iter_reference_grades(cases, answers, llm):
            file.write(
                json.dumps(
                    graded_row.model_dump(mode="json"),
                    ensure_ascii=False,
                )
                + "\n"
            )
            file.flush()
            completed += 1
            passed += graded_row.grade.matches_reference
            print(
                f"Graded {graded_row.id}: {graded_row.grade.matches_reference}",
                flush=True,
            )
finally:
    metadata.update(
        status="completed" if completed == len(cases) else "incomplete",
        graded_cases=completed,
        passed_cases=passed,
        updated_at=datetime.now(UTC).isoformat(),
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    wait_for_all_tracers()

print(f"Grade coverage: {completed}/{len(cases)}")
print(f"Reference match rate: {passed}/{completed} ({passed / completed:.1%})")
print(f"Saved grades to {output}")
