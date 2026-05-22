#!/usr/bin/env python3
"""Run request-path coupled ResidentClaim offload lifecycle evidence."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter.live_request_path import (  # noqa: E402
    INSTRUMENTATION_SCOPE,
    LiveRequestRecord,
    build_request_coupled_trace,
    evaluate_request_coupled_trace,
    request_metrics,
)
from kv_vllm_arbiter.offload_lifecycle import write_jsonl  # noqa: E402


DEFAULT_OUT_DIR = ROOT / "artifacts" / "live_request_path"
DEFAULT_MODEL = os.environ.get(
    "VLLM_KV_RESIDENCY_MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct"
)
AUDIT_PYTHON = os.environ.get("VLLM_AUDIT_PYTHON")
VLLM_SOURCE = os.environ.get("VLLM_KV_RESIDENCY_VLLM_SOURCE")

MODES = (
    ("no_hook", "baseline_no_hook", False),
    ("hook_integrated_event_emission_disabled", "positive_bundle", False),
    ("hook_integrated_event_emission_enabled", "positive_bundle", True),
    ("false_positive_generic_substrate", "generic_substrate", True),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--run-id", default="live-request-path-coupled-reference")
    parser.add_argument("--max-model-len", type=int, default=512)
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.35)
    parser.add_argument("--kv-cache-memory-bytes", type=int, default=None)
    parser.add_argument("--require-vllm", action="store_true")
    parser.add_argument("--use-source-tree", action="store_true")
    return parser.parse_args()


def ensure_selected_python() -> None:
    if not AUDIT_PYTHON:
        return
    audit_python = Path(AUDIT_PYTHON).expanduser()
    if audit_python.exists() and Path(sys.executable).resolve() != audit_python.resolve():
        os.execv(str(audit_python), [str(audit_python), *sys.argv])


def maybe_add_source_tree(args: argparse.Namespace) -> None:
    if not (args.use_source_tree or os.environ.get("VLLM_KV_RESIDENCY_USE_SOURCE_TREE") == "1"):
        return
    if not VLLM_SOURCE:
        return
    source = Path(VLLM_SOURCE).expanduser()
    if source.exists():
        sys.path.insert(0, str(source))


def import_runtime() -> tuple[Any | None, Any | None, str | None]:
    try:
        from vllm import LLM, SamplingParams

        return LLM, SamplingParams, None
    except Exception as exc:
        return None, None, f"{type(exc).__name__}: {exc}"


def make_prompts() -> list[tuple[str, str]]:
    prefix = (
        "Resident KV request-path prefix. Preserve this stable context. "
        "The repeated text is intentionally shared for prefix-cache observation. "
        * 18
    )
    return [
        (
            "resident",
            prefix + "\nResident turn: answer with a short sentence.",
        ),
        (
            "reuse",
            prefix + "\nReuse turn: answer with a different short sentence.",
        ),
        (
            "failure",
            prefix + "\nFailure-control turn: this request is refused by the harness.",
        ),
    ]


def metrics_to_record(metrics: Any) -> dict[str, Any]:
    if metrics is None:
        return {}
    names = [
        "arrival_time",
        "queued_ts",
        "scheduled_ts",
        "first_token_ts",
        "last_token_ts",
        "first_token_latency",
        "num_generation_tokens",
    ]
    return {name: getattr(metrics, name) for name in names if hasattr(metrics, name)}


def output_record(role: str, output: Any, started: float, ended: float) -> dict[str, Any]:
    generated_tokens = sum(len(item.token_ids) for item in output.outputs)
    return {
        "role": role,
        "request_id": output.request_id,
        "wall_latency_s": ended - started,
        "ttft_s": getattr(output.metrics, "first_token_latency", None)
        if output.metrics is not None
        else None,
        "num_prompt_tokens": len(output.prompt_token_ids or []),
        "num_cached_tokens": output.num_cached_tokens,
        "num_output_tokens": generated_tokens,
        "metrics": metrics_to_record(output.metrics),
        "status": "served",
    }


def run_vllm_requests(args: argparse.Namespace, LLM: Any, SamplingParams: Any) -> list[LiveRequestRecord]:
    os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")
    llm_kwargs: dict[str, Any] = {
        "model": str(args.model),
        "trust_remote_code": True,
        "dtype": "half",
        "max_model_len": args.max_model_len,
        "enable_prefix_caching": True,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "enforce_eager": True,
        "disable_log_stats": False,
    }
    if args.kv_cache_memory_bytes is not None:
        llm_kwargs["kv_cache_memory_bytes"] = args.kv_cache_memory_bytes

    llm = LLM(**llm_kwargs)
    sampling = SamplingParams(temperature=0, max_tokens=args.max_tokens, ignore_eos=True)

    records: list[LiveRequestRecord] = []
    for role, prompt in make_prompts():
        if role == "failure":
            started = time.perf_counter()
            ended = time.perf_counter()
            records.append(
                LiveRequestRecord(
                    role=role,
                    request_id=f"{len(records)}",
                    wall_latency_s=ended - started,
                    ttft_s=None,
                    num_prompt_tokens=None,
                    num_cached_tokens=None,
                    num_output_tokens=0,
                    status="controlled_refusal_by_harness",
                )
            )
            continue
        started = time.perf_counter()
        output = llm.generate([prompt], sampling, use_tqdm=False)[0]
        ended = time.perf_counter()
        records.append(LiveRequestRecord.from_mapping(output_record(role, output, started, ended)))
    return records


def blocked_payload(args: argparse.Namespace, reason: str) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "blocked_missing_vllm_runtime",
        "blocked_reason": reason,
        "python": sys.executable,
        "audit_python": AUDIT_PYTHON,
        "vllm_source": VLLM_SOURCE,
        "model": str(args.model),
        "instrumentation_scope": INSTRUMENTATION_SCOPE,
        "claim_boundary": (
            "No live request-path evidence collected; vLLM and torch were not "
            "importable in the selected Python."
        ),
    }


def mode_record(
    label: str,
    scenario: str,
    emit_events: bool,
    *,
    request_records: list[LiveRequestRecord],
    out_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    start = time.perf_counter_ns()
    events = build_request_coupled_trace(
        request_records,
        run_id=f"{run_id}:{label}",
        scenario=scenario,
        emit_events=emit_events,
    )
    trace_build_ns = time.perf_counter_ns() - start
    jsonl_path = out_dir / f"{label}.jsonl"
    write_jsonl(jsonl_path, events)

    analyzer_start = time.perf_counter_ns()
    evaluation = evaluate_request_coupled_trace(events)
    analyzer_ns = time.perf_counter_ns() - analyzer_start

    return {
        "label": label,
        "scenario": scenario,
        "hook_event_emission_enabled": emit_events,
        "jsonl": artifact_path(jsonl_path),
        "event_volume": len(events),
        "event_bytes": jsonl_path.stat().st_size,
        "trace_build_ns": trace_build_ns,
        "analyzer_runtime_ns": analyzer_ns,
        "request_metrics": request_metrics(request_records),
        "passes_reference_gate": evaluation["passes_reference_gate"],
        "reference_missing_requirements": evaluation["gate_summary"][
            "reference_missing_requirements"
        ],
        "contract_event_order": evaluation["contract_event_order"],
        "event_counts": evaluation["event_counts"],
        "active_claim_count": evaluation["active_claim_count"],
        "claim_registry_size": evaluation["claim_registry_size"],
        "instrumentation_scope": INSTRUMENTATION_SCOPE,
        "native_vllm_offload_claimed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    if payload["status"] != "ok":
        return (
            "# Live Request-Path Harness\n\n"
            f"Status: `{payload['status']}`\n\n"
            f"Reason: {payload['blocked_reason']}\n\n"
            "No live serving evidence was collected in this run.\n"
        )

    records = payload["records"]
    lines = [
        "# Live Request-Path Harness",
        "",
        "Scope: request-path coupled reference instrumentation, not native vLLM offload.",
        "",
        "| Mode | Gate | Events | Bytes | Mean latency s | Mean TTFT s | Analyzer ns | Missing requirements |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for record in records:
        missing = ", ".join(record["reference_missing_requirements"]) or "-"
        metrics = record["request_metrics"]
        lines.append(
            "| "
            f"{record['label']} | "
            f"{'pass' if record['passes_reference_gate'] else 'fail'} | "
            f"{record['event_volume']} | "
            f"{record['event_bytes']} | "
            f"{metrics['latency_s_mean']} | "
            f"{metrics['ttft_s_mean']} | "
            f"{record['analyzer_runtime_ns']} | "
            f"{missing} |"
        )
    lines.extend(["", "## Request Records", ""])
    for record in payload["request_records"]:
        lines.append(
            f"- `{record['role']}` request `{record['request_id']}`: "
            f"status `{record['status']}`, latency `{record['wall_latency_s']}` s, "
            f"TTFT `{record['ttft_s']}` s."
        )
    lines.append("")
    return "\n".join(lines)


def artifact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def overhead(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_label = {record["label"]: record for record in records}
    baseline = by_label["no_hook"]
    enabled = by_label["hook_integrated_event_emission_enabled"]
    disabled = by_label["hook_integrated_event_emission_disabled"]
    base_latency = baseline["request_metrics"]["latency_s_sum"]
    enabled_latency = enabled["request_metrics"]["latency_s_sum"]
    disabled_latency = disabled["request_metrics"]["latency_s_sum"]
    return {
        "enabled_event_volume_minus_no_hook": (
            enabled["event_volume"] - baseline["event_volume"]
        ),
        "enabled_event_bytes_minus_no_hook": (
            enabled["event_bytes"] - baseline["event_bytes"]
        ),
        "enabled_analyzer_runtime_ns": enabled["analyzer_runtime_ns"],
        "enabled_trace_build_ns_minus_disabled": (
            enabled["trace_build_ns"] - disabled["trace_build_ns"]
        ),
        "enabled_latency_s_minus_no_hook": round(enabled_latency - base_latency, 6)
        if enabled_latency is not None and base_latency is not None
        else None,
        "enabled_latency_s_minus_disabled": round(enabled_latency - disabled_latency, 6)
        if enabled_latency is not None and disabled_latency is not None
        else None,
    }


def main() -> int:
    args = parse_args()
    ensure_selected_python()
    maybe_add_source_tree(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    LLM, SamplingParams, import_error = import_runtime()
    if import_error is not None:
        payload = blocked_payload(args, import_error)
        write_outputs(args.out_dir, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2 if args.require_vllm else 0

    request_records = run_vllm_requests(args, LLM, SamplingParams)
    records = [
        mode_record(
            label,
            scenario,
            emit_events,
            request_records=request_records,
            out_dir=args.out_dir,
            run_id=args.run_id,
        )
        for label, scenario, emit_events in MODES
    ]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok",
        "model": str(args.model),
        "python": sys.executable,
        "instrumentation_scope": INSTRUMENTATION_SCOPE,
        "claim_boundary": (
            "Request ids and timings come from vLLM LLM.generate where vLLM is "
            "available; offload lifecycle/outcome transitions are produced by "
            "the reference hook and are not native vLLM host-offload evidence."
        ),
        "request_records": [record.to_record() for record in request_records],
        "records": records,
        "overhead": overhead(records),
    }
    write_outputs(args.out_dir, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def write_outputs(out_dir: Path, payload: dict[str, Any]) -> None:
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
