"""Prepare, execute, grade, and report an evaluation with one command."""

import argparse
import json
import os
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


@contextmanager
def use_chat_model(model: str):
    previous = os.environ.get("ARCHIVIST_CHAT_MODEL")
    os.environ["ARCHIVIST_CHAT_MODEL"] = model
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ARCHIVIST_CHAT_MODEL", None)
        else:
            os.environ["ARCHIVIST_CHAT_MODEL"] = previous


def run_stage(name: str, *arguments: str) -> dict:
    previous = sys.argv
    sys.argv = [name, *arguments]
    try:
        print(f"Running {name}", flush=True)
        return runpy.run_path(
            str(SCRIPTS_DIR / name),
            run_name="__main__",
        )
    finally:
        sys.argv = previous


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--chat-model", required=True)
parser.add_argument("--chat-variant", required=True)
parser.add_argument("--judge-model", required=True)
parser.add_argument("--judge-variant", required=True)
args = parser.parse_args()

with use_chat_model(args.chat_model):
    prepared = run_stage(
        "prepare_eval_run.py",
        "--chat-variant",
        args.chat_variant,
    )
    run_dir = prepared["run_dir"]
    run_stage("run_eval.py", str(run_dir))

with use_chat_model(args.judge_model):
    graded = run_stage(
        "judge_batch.py",
        str(run_dir),
        "--judge-variant",
        args.judge_variant,
    )
    grade_dir = graded["grade_dir"]

reported = run_stage("report_eval.py", str(run_dir), str(grade_dir))
report_path = run_dir / "report.json"
with report_path.open("x", encoding="utf-8") as file:
    file.write(json.dumps(reported["report"], indent=2, ensure_ascii=False) + "\n")

print(f"Saved report to {report_path}")
