#!/usr/bin/env python3
"""Evaluate the reference offload lifecycle/outcome hook."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter.offload_lifecycle import (  # noqa: E402
    build_reference_trace,
    evaluate_offload_lifecycle_events,
    write_jsonl,
)


DEFAULT_OUT_DIR = ROOT / "artifacts" / "offload_lifecycle"
SCENARIOS = [
    ("baseline_no_offload_hook", "baseline_no_hook", False),
    ("positive_bundle_hook_disabled", "positive_bundle", False),
    ("success_restore", "success_restore", True),
    ("failure_refusal", "failure_refusal", True),
    ("positive_bundle", "positive_bundle", True),
    ("false_positive_generic_substrate", "generic_substrate", True),
    ("false_positive_offload_no_restore", "claim_offload_no_restore", True),
    ("false_positive_restore_after_reuse", "restore_after_reuse", True),
    ("false_positive_wrong_claim_outcome", "wrong_claim_failure_outcome", True),
    ("false_positive_fallback_recompute", "fallback_recompute", True),
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--iterations", type=int, default=1000)
    return parser


def timed_build(
    scenario: str,
    *,
    emit_events: bool,
    iterations: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    latencies = []
    last_events: list[dict[str, Any]] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        last_events = build_reference_trace(scenario, emit_events=emit_events)
        latencies.append(time.perf_counter_ns() - start)

    return last_events, {
        "iterations": iterations,
        "trace_generation_latency_ns_mean": round(statistics.mean(latencies), 1),
        "trace_generation_latency_ns_median": round(statistics.median(latencies), 1),
        "trace_generation_latency_ns_min": min(latencies),
        "trace_generation_latency_ns_max": max(latencies),
        "trace_generation_throughput_traces_per_s": round(
            1_000_000_000 / statistics.mean(latencies),
            2,
        )
        if latencies and statistics.mean(latencies) > 0
        else None,
    }


def scenario_record(
    label: str,
    scenario: str,
    *,
    emit_events: bool,
    out_dir: Path,
    iterations: int,
) -> dict[str, Any]:
    events, latency_metrics = timed_build(
        scenario,
        emit_events=emit_events,
        iterations=iterations,
    )
    jsonl_path = out_dir / f"{label}.jsonl"
    summary_path = out_dir / f"{label}_summary.json"
    gate_summary_path = out_dir / f"{label}_gate_summary.json"
    write_jsonl(jsonl_path, events)

    rel_jsonl = artifact_path(jsonl_path)
    analyzer_start = time.perf_counter_ns()
    evaluation = evaluate_offload_lifecycle_events(
        events,
        evidence_path=rel_jsonl,
    )
    analyzer_runtime_ns = time.perf_counter_ns() - analyzer_start

    gate_summary_path.write_text(
        json.dumps(evaluation.gate_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    record = {
        "label": label,
        "scenario": scenario,
        "hook_event_emission_enabled": emit_events,
        "jsonl": rel_jsonl,
        "gate_summary": artifact_path(gate_summary_path),
        "event_volume": len(events),
        "event_bytes": jsonl_path.stat().st_size,
        "analyzer_runtime_ns": analyzer_runtime_ns,
        "active_claim_count": evaluation.active_claim_count,
        "claim_registry_size": evaluation.claim_registry_size,
        "event_counts": evaluation.event_counts,
        "passes_reference_gate": evaluation.passes_reference_gate,
        "reference_missing_requirements": evaluation.gate_summary[
            "reference_missing_requirements"
        ],
        **latency_metrics,
    }
    summary_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record


def render_markdown(records: list[dict[str, Any]], overhead: dict[str, Any]) -> str:
    lines = [
        "# Reference Offload Lifecycle Hook Evaluation",
        "",
        "Scope: executable reference state-machine hook, not production vLLM host-offload performance.",
        "",
        "| Scenario | Gate | Events | Bytes | Mean trace ns | Trace/s | Analyzer ns | Missing requirements |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for record in records:
        missing = ", ".join(record["reference_missing_requirements"]) or "-"
        lines.append(
            "| "
            f"{record['label']} | "
            f"{'pass' if record['passes_reference_gate'] else 'fail'} | "
            f"{record['event_volume']} | "
            f"{record['event_bytes']} | "
            f"{record['trace_generation_latency_ns_mean']} | "
            f"{record['trace_generation_throughput_traces_per_s']} | "
            f"{record['analyzer_runtime_ns']} | "
            f"{missing} |"
        )
    lines.extend(
        [
            "",
            "## Overhead",
            "",
            "| Comparison | Value |",
            "|---|---:|",
        ]
    )
    for key, value in overhead.items():
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines) + "\n"


def artifact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    records = [
        scenario_record(
            label,
            scenario,
            emit_events=emit_events,
            out_dir=args.out_dir,
            iterations=args.iterations,
        )
        for label, scenario, emit_events in SCENARIOS
    ]
    by_label = {record["label"]: record for record in records}
    baseline = by_label["baseline_no_offload_hook"]
    emission_disabled = by_label["positive_bundle_hook_disabled"]
    positive = by_label["positive_bundle"]
    overhead = {
        "positive_bundle_mean_ns_minus_baseline_no_hook_mean_ns": round(
            positive["trace_generation_latency_ns_mean"]
            - baseline["trace_generation_latency_ns_mean"],
            1,
        ),
        "positive_bundle_mean_ns_over_baseline_no_hook_mean_ns": round(
            positive["trace_generation_latency_ns_mean"]
            / baseline["trace_generation_latency_ns_mean"],
            3,
        )
        if baseline["trace_generation_latency_ns_mean"]
        else None,
        "positive_bundle_mean_ns_minus_event_emission_disabled_mean_ns": round(
            positive["trace_generation_latency_ns_mean"]
            - emission_disabled["trace_generation_latency_ns_mean"],
            1,
        ),
        "positive_bundle_mean_ns_over_event_emission_disabled_mean_ns": round(
            positive["trace_generation_latency_ns_mean"]
            / emission_disabled["trace_generation_latency_ns_mean"],
            3,
        )
        if emission_disabled["trace_generation_latency_ns_mean"]
        else None,
        "positive_bundle_events": positive["event_volume"],
        "positive_bundle_event_bytes": positive["event_bytes"],
        "positive_bundle_analyzer_runtime_ns": positive["analyzer_runtime_ns"],
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "iterations": args.iterations,
        "scope": (
            "Reference lifecycle/outcome conformance witness for ResidentClaim "
            "offloadable semantics; trace-generation metrics are not serving "
            "throughput or production offload performance."
        ),
        "records": records,
        "overhead": overhead,
    }
    (args.out_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "summary.md").write_text(
        render_markdown(records, overhead),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
