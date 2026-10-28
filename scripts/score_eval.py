"""Calculate source recall from saved evaluation results."""

import argparse
import json
from pathlib import Path
from statistics import mean

from archivist.evaluation import load_eval_cases, source_recall

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("results", type=Path)
args = parser.parse_args()

cases = load_eval_cases(Path("evals/cases.json"), Path("evals/corpus"))
rows = [
    json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines()
]

by_id = {}
for row in rows:
    if row["id"] in by_id:
        raise ValueError(f"Duplicate result ID: {row['id']}")
    by_id[row["id"]] = row

if set(by_id) != {case.id for case in cases}:
    raise ValueError("Result IDs do not match dataset IDs")

scores = []
for case in cases:
    row = by_id[case.id]
    if row["question"] != case.question:
        raise ValueError(f"Question mismatch: {case.id}")

    score = source_recall(
        case.expected_sources,
        [hit["source"] for hit in row["retrieved"]],
    )
    if score is None:
        print(f"{case.id}: N/A (unanswerable)")
        continue

    scores.append(score)
    print(f"{case.id}: {score:.1%}")

if scores:
    print(f"Mean source recall ({len(scores)} cases): {mean(scores):.1%}")
else:
    print("Mean source recall: N/A (no answerable cases)")
