#!/usr/bin/env python3
"""Run claim expiry and demotion lifecycle probes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PYTHON = Path(os.environ.get("VLLM_AUDIT_PYTHON", sys.executable))
PROBE = ROOT / "scripts" / "run_blockpool_contract_probe.py"
OUT_DIR = ROOT / "artifacts" / "claim_lifecycle"


def run_case(name: str, extra_args: list[str]) -> dict:
    jsonl = OUT_DIR / f"{name}.jsonl"
    summary = OUT_DIR / f"{name}_summary.json"
    args = [
        str(AUDIT_PYTHON),
        str(PROBE),
        "--run-id",
        f"claim-lifecycle-{name}",
        "--policy",
        f"claim_lifecycle_{name}",
        "--resident-claim",
        "--enforce-hard-exclude",
        "--jsonl",
        str(jsonl),
        "--summary",
        str(summary),
        *extra_args,
    ]
    subprocess.run(args, check=True, stdout=subprocess.PIPE, text=True)
    return json.loads(summary.read_text())


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [
        run_case("expire", ["--claim-ttl-allocations", "1"]),
        run_case("demote", ["--on-conflict", "demote"]),
    ]
    result = {"rows": rows}
    output = OUT_DIR / "claim_lifecycle_results.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
