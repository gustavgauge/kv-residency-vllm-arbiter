#!/usr/bin/env python3
"""Run the capacity sweep for native/no-admit/hard-claim behavior."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PYTHON = Path(os.environ.get("VLLM_AUDIT_PYTHON", sys.executable))
PROBE = ROOT / "scripts" / "run_blockpool_contract_probe.py"
CONFIG = ROOT / "experiments" / "capacity_sweep.json"
OUT_DIR = ROOT / "artifacts" / "capacity_sweep"

sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter.trace_summary import (  # noqa: E402
    classify_active_resident_outcome,
    load_jsonl,
)


POLICIES = ("native", "write_no_admit", "hard_resident_exclude")


def artifact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def run_probe(policy: str, usable_blocks: int, scenario: dict) -> dict:
    stem = f"{policy}_{usable_blocks}"
    jsonl = OUT_DIR / f"{stem}.jsonl"
    summary = OUT_DIR / f"{stem}_probe_summary.json"
    args = [
        str(AUDIT_PYTHON),
        str(PROBE),
        "--resident-blocks",
        str(scenario["resident_blocks"]),
        "--active-blocks",
        str(scenario["active_live_blocks"]),
        "--block-size",
        str(scenario["block_size_tokens"]),
        "--usable-blocks",
        str(usable_blocks),
        "--run-id",
        f"capacity-sweep-{policy}-{usable_blocks}",
        "--policy",
        policy,
        "--jsonl",
        str(jsonl),
        "--summary",
        str(summary),
    ]
    if policy == "write_no_admit":
        args.append("--no-admit-active")
    if policy == "hard_resident_exclude":
        args.extend(["--resident-claim", "--enforce-hard-exclude"])

    subprocess.run(args, check=True, stdout=subprocess.PIPE, text=True)
    outcome = classify_active_resident_outcome(load_jsonl(jsonl)).to_record()
    probe_summary = json.loads(summary.read_text())
    outcome.update(
        {
            "resident_blocks": scenario["resident_blocks"],
            "active_live_blocks": scenario["active_live_blocks"],
            "total_required_blocks": (
                scenario["resident_blocks"] + scenario["active_live_blocks"]
            ),
            "free_blocks_before_active": probe_summary["free_blocks_before_active"],
            "remaining_cached_resident_blocks": probe_summary[
                "remaining_cached_resident_blocks"
            ],
            "active_allocated": probe_summary["active_allocated"],
            "active_future_reuse_admitted": probe_summary[
                "active_future_reuse_admitted"
            ],
            "jsonl": artifact_path(jsonl),
        }
    )
    return outcome


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "# Capacity Sweep",
        "",
        "| Usable | Policy | Active action | Active served | Resident preserved | Resident victims | Active reusable |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {usable_blocks} | {policy} | {active_action} | {active_served} | "
            "{resident_preserved} | {cached_resident_victims} | "
            "{active_future_reuse_admitted} |".format(**row)
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    scenario = config["scenario"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for usable_blocks in config["usable_blocks"]:
        for policy in POLICIES:
            rows.append(run_probe(policy, usable_blocks, scenario))

    result = {
        "scenario": scenario,
        "policies": list(POLICIES),
        "rows": rows,
    }
    json_path = OUT_DIR / "capacity_sweep_results.json"
    md_path = OUT_DIR / "capacity_sweep_summary.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_markdown(rows))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
