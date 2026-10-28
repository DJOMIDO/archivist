"""Validate manual reviews against saved evaluation results."""

import argparse
from pathlib import Path

from archivist.evaluation import load_reviews

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("reviews", type=Path)
parser.add_argument("results", type=Path)
args = parser.parse_args()

data = load_reviews(args.reviews, args.results)

print(f"Validated {len(data.reviews)} reviews for {data.run_file}.")
