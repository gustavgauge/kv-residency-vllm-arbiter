#!/usr/bin/env python3
"""Run the hard resident claim probe."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PYTHON = Path(os.environ.get("VLLM_AUDIT_PYTHON", sys.executable))


def main() -> int:
    script = ROOT / "scripts" / "run_blockpool_contract_probe.py"
    jsonl = ROOT / "artifacts" / "hard_claim" / "hard_claim_60_70_80.jsonl"
    summary = (
        ROOT
        / "artifacts"
        / "hard_claim"
        / "hard_claim_60_70_80_summary.json"
    )
    os.execv(
        str(AUDIT_PYTHON),
        [
            str(AUDIT_PYTHON),
            str(script),
            "--run-id",
            "hard-claim-60-70-80",
            "--policy",
            "hard_resident_exclude",
            "--resident-claim",
            "--enforce-hard-exclude",
            "--jsonl",
            str(jsonl),
            "--summary",
            str(summary),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
