"""Print content fingerprints for the evaluation dataset."""

import json
from dataclasses import asdict
from pathlib import Path

from archivist.evaluation import fingerprint_eval_data

fingerprints = fingerprint_eval_data(
    Path("evals/cases.json"),
    Path("evals/corpus"),
)

print(json.dumps(asdict(fingerprints), indent=2, ensure_ascii=False))
