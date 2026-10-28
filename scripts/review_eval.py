"""Display one saved answer and its evidence for manual review."""

import argparse
import json
from pathlib import Path

from archivist.evaluation import load_eval_cases

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("results", type=Path)
parser.add_argument("case_id")
args = parser.parse_args()

corpus = Path("evals/corpus")
cases = load_eval_cases(Path("evals/cases.json"), corpus)
rows = [
    json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines()
]

case = next(case for case in cases if case.id == args.case_id)
row = next(row for row in rows if row["id"] == args.case_id)

print(f"Question: {case.question}")
print(f"Reference: {case.reference_answer}")

for number, hit in enumerate(row["retrieved"], start=1):
    source = hit["source"]
    print(f"\n[{number}] {source}")
    print((corpus / source).read_text(encoding="utf-8"))

print(f"\nAnswer: {row['answer']}")
print(f"Cited sources: {row['cited_sources']}")
