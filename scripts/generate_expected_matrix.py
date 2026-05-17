#!/usr/bin/env python3
"""Generate the expected active/resident capacity matrix."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter import CapacityCase, classify_policy  # noqa: E402


def main() -> int:
    config_path = ROOT / "experiments" / "capacity_sweep.json"
    config = json.loads(config_path.read_text())
    scenario = config["scenario"]

    rows = []
    for usable_blocks in config["usable_blocks"]:
        case = CapacityCase(
            resident_blocks=scenario["resident_blocks"],
            active_live_blocks=scenario["active_live_blocks"],
            usable_blocks=usable_blocks,
        )
        for policy in config["policies"]:
            outcome = classify_policy(policy, case)
            rows.append(
                {
                    "usable_blocks": usable_blocks,
                    "policy": policy,
                    "resident_preserved": outcome.resident_preserved,
                    "active_served": outcome.active_served,
                    "active_reusable": outcome.active_reusable,
                    "arbiter_action": outcome.arbiter_action,
                    "explanation": outcome.explanation,
                }
            )

    print(json.dumps({"scenario": scenario, "rows": rows}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
