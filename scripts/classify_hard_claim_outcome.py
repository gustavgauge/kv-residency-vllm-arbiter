#!/usr/bin/env python3
"""Classify active/resident outcome from telemetry without log scraping."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter.trace_summary import (  # noqa: E402
    classify_active_resident_outcome,
    load_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "jsonl",
        type=Path,
        nargs="?",
        default=ROOT
        / "artifacts"
        / "hard_claim"
        / "hard_claim_60_70_80.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "artifacts"
        / "outcome_classification"
        / "hard_claim_outcome_60_70_80.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outcome = classify_active_resident_outcome(load_jsonl(args.jsonl)).to_record()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
