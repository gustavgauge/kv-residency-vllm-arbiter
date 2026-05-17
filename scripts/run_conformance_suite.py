#!/usr/bin/env python3
"""Generate ResidentClaim conformance artifacts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PYTHON = Path(os.environ.get("VLLM_AUDIT_PYTHON", sys.executable))
PROBE = ROOT / "scripts" / "run_blockpool_contract_probe.py"
OUT_DIR = ROOT / "artifacts" / "conformance"


def ensure_import_path() -> None:
    sys.path.insert(0, str(ROOT / "src"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def run_probe(name: str, policy: str, extra_args: list[str]) -> tuple[dict, list[dict]]:
    jsonl = OUT_DIR / f"{name}.jsonl"
    summary = OUT_DIR / f"{name}_summary.json"
    args = [
        str(AUDIT_PYTHON),
        str(PROBE),
        "--run-id",
        f"conformance-{name}",
        "--policy",
        policy,
        "--jsonl",
        str(jsonl),
        "--summary",
        str(summary),
        *extra_args,
    ]
    subprocess.run(args, check=True, stdout=subprocess.PIPE, text=True)
    return json.loads(summary.read_text()), load_jsonl(jsonl)


def status_counts(results: list[Any]) -> dict[str, int]:
    return {
        status: sum(1 for result in results if result.status.value == status)
        for status in sorted({result.status.value for result in results})
    }


def main() -> int:
    ensure_import_path()

    from kv_vllm_arbiter.conformance import (
        ConformanceResult,
        ConformanceStatus,
        backend_approximation_litmus,
        event_counts,
        evaluate_demotion_or_expiry_before_loss,
        evaluate_hard_claim_infeasibility,
        evaluate_no_accepted_claim_no_harm,
        evaluate_write_no_admit_separation,
        materialization_predicate_litmus,
        render_results_markdown,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    native_summary, native_events = run_probe(
        "L1_native_no_claim",
        "native",
        [],
    )
    no_admit_summary, no_admit_events = run_probe(
        "L2_write_no_admit",
        "write_no_admit",
        ["--no-admit-active"],
    )
    hard_summary, hard_events = run_probe(
        "L3_hard_claim_infeasibility",
        "hard_claim_infeasibility",
        ["--resident-claim", "--enforce-hard-exclude"],
    )
    demote_summary, demote_events = run_probe(
        "L4_demote_before_loss",
        "demotion_before_loss",
        ["--resident-claim", "--enforce-hard-exclude", "--on-conflict", "demote"],
    )
    expire_summary, expire_events = run_probe(
        "L5_expiry_before_loss",
        "expiry_before_loss",
        [
            "--resident-claim",
            "--enforce-hard-exclude",
            "--claim-ttl-allocations",
            "1",
        ],
    )
    hard_claim_result = evaluate_hard_claim_infeasibility(
        summary=hard_summary,
        events=hard_events,
        evidence=(
            "artifacts/conformance/L3_hard_claim_infeasibility.jsonl",
            "artifacts/conformance/L3_hard_claim_infeasibility_summary.json",
        ),
    )
    hard_event_counts = event_counts(hard_events)
    trace_reconstructs = (
        hard_claim_result.status == ConformanceStatus.PASS
        and hard_event_counts.get("resident_claim_accepted", 0) == 1
        and hard_event_counts.get("resident_claim_materialized", 0) == 1
        and hard_event_counts.get("active_request_refused", 0) == 1
    )

    results = [
        evaluate_no_accepted_claim_no_harm(
            summary=native_summary,
            events=native_events,
            evidence=(
                "artifacts/conformance/L1_native_no_claim.jsonl",
                "artifacts/conformance/L1_native_no_claim_summary.json",
            ),
        ),
        evaluate_write_no_admit_separation(
            summary=no_admit_summary,
            events=no_admit_events,
            evidence=(
                "artifacts/conformance/L2_write_no_admit.jsonl",
                "artifacts/conformance/L2_write_no_admit_summary.json",
            ),
        ),
        hard_claim_result,
        evaluate_demotion_or_expiry_before_loss(
            litmus_id="L4",
            title="Demotion precedes later block loss",
            release_event="resident_claim_demoted",
            summary=demote_summary,
            events=demote_events,
            evidence=(
                "artifacts/conformance/L4_demote_before_loss.jsonl",
                "artifacts/conformance/L4_demote_before_loss_summary.json",
            ),
        ),
        evaluate_demotion_or_expiry_before_loss(
            litmus_id="L5",
            title="Expiry precedes later block loss",
            release_event="resident_claim_expired",
            summary=expire_summary,
            events=expire_events,
            evidence=(
                "artifacts/conformance/L5_expiry_before_loss.jsonl",
                "artifacts/conformance/L5_expiry_before_loss_summary.json",
            ),
        ),
        materialization_predicate_litmus(
            evidence=(
                "kv-residency-microruntime/tests/test_resident_claim_contract.py",
                "kv-residency-microruntime/tests/test_materialization_fidelity.py",
            )
        ),
        ConformanceResult(
            litmus_id="L7",
            title="Event trace reconstructs active/resident outcome",
            status=(
                ConformanceStatus.PASS
                if trace_reconstructs
                else ConformanceStatus.FAIL
            ),
            required_observation=(
                "An observer must reconstruct acceptance, materialization, "
                "active conflict, blocking claim IDs, and final outcome from "
                "the trace."
            ),
            observed=(
                "hard-claim trace includes accepted+materialized lifecycle "
                "events and attributed active refusal."
            ),
            evidence=(
                "artifacts/conformance/L3_hard_claim_infeasibility.jsonl",
                "artifacts/conformance/L3_hard_claim_infeasibility_summary.json",
            ),
            fields={
                "hard_claim_summary": hard_summary,
                "event_counts": hard_event_counts,
            },
        ),
        backend_approximation_litmus(
            evidence=(
                "scripts/generate_prior_art_boundary.py",
                "artifacts/prior_art/prior_art_boundary.md",
            )
        ),
    ]

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "conformance_scope": (
            "ResidentClaim conformance suite with executable direct vLLM traces "
            "for claim acceptance, materialization, active infeasibility "
            "attribution, demotion/expiry-before-loss, no-admit separation, "
            "and materialization-predicate failure, plus one backend capability "
            "classification check."
        ),
        "status_counts": status_counts(results),
        "results": [result.to_record() for result in results],
    }
    (OUT_DIR / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (OUT_DIR / "summary.md").write_text(render_results_markdown(results))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
