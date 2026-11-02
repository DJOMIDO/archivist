"""Summarize validated manual reviews with explicit coverage."""

import argparse
import json
from pathlib import Path

from archivist.evaluation import (
    load_eval_cases,
    load_reviews,
    summarize_reviews,
)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("reviews", type=Path)
parser.add_argument("results", type=Path)
args = parser.parse_args()

cases = load_eval_cases(Path("evals/cases.json"), Path("evals/corpus"))
data = load_reviews(args.reviews, args.results)
rows = [
    json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines()
]

by_id = {row["id"]: row for row in rows}
if set(by_id) != {case.id for case in cases}:
    raise ValueError("Result IDs do not match dataset IDs")

for case in cases:
    if by_id[case.id]["question"] != case.question:
        raise ValueError(f"Question mismatch: {case.id}")

summary = summarize_reviews(cases, data)
total = summary.total
reviewed = summary.reviewed

print(f"Review coverage: {reviewed}/{total} ({reviewed / total:.1%})")

for field, passed in summary.passed.items():
    print(f"{field}: {passed}/{reviewed} ({passed / reviewed:.1%})")

print(
    f"All criteria passed among reviewed answers: "
    f"{summary.all_passed}/{reviewed} "
    f"({summary.all_passed / reviewed:.1%})"
)

if summary.pending:
    print("Full-dataset answer pass rate: N/A (incomplete review coverage)")
    print(f"Pending: {', '.join(summary.pending)}")
else:
    print(f"Full-dataset answer pass rate: {summary.all_passed / total:.1%}")
