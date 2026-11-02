"""Report metrics from a completed answer run and reference-grading batch."""

import argparse
import json
from pathlib import Path

from archivist.evaluation import build_eval_report

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run_dir", type=Path)
parser.add_argument("grade_dir", type=Path)
args = parser.parse_args()

report = build_eval_report(args.run_dir, args.grade_dir)
print(json.dumps(report, indent=2, ensure_ascii=False))
