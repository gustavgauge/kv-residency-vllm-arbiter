#!/usr/bin/env python3
"""Run the write no-admit separation probe."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PYTHON = Path(os.environ.get("VLLM_AUDIT_PYTHON", sys.executable))


def main() -> int:
    script = ROOT / "scripts" / "run_blockpool_contract_probe.py"
    jsonl = ROOT / "artifacts" / "no_admit" / "no_admit_60_70_80.jsonl"
    summary = (
        ROOT
        / "artifacts"
        / "no_admit"
        / "no_admit_60_70_80_summary.json"
    )
    os.execv(
        str(AUDIT_PYTHON),
        [
            str(AUDIT_PYTHON),
            str(script),
            "--run-id",
            "no-admit-60-70-80",
            "--policy",
            "write_no_admit",
            "--no-admit-active",
            "--jsonl",
            str(jsonl),
            "--summary",
            str(summary),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
