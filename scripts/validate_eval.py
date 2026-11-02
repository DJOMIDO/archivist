"""Validate the evaluation dataset from the project root."""

from pathlib import Path

from archivist.evaluation import load_eval_cases

cases = load_eval_cases(
    Path("evals/cases.json"),
    Path("evals/corpus"),
)
print(f"Validated {len(cases)} cases.")
