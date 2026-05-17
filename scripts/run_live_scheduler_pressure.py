#!/usr/bin/env python3
"""Run a live vLLM scheduler pressure case with protected resident claims."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PYTHON = os.environ.get("VLLM_AUDIT_PYTHON")
DEFAULT_MODEL = os.environ.get(
    "VLLM_KV_RESIDENCY_MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct"
)
VLLM_SOURCE = os.environ.get("VLLM_KV_RESIDENCY_VLLM_SOURCE")


class GenerateTimeout(TimeoutError):
    pass


def ensure_audit_runtime() -> None:
    if AUDIT_PYTHON:
        audit_python = Path(AUDIT_PYTHON).expanduser()
        if (
            Path(sys.executable).resolve() != audit_python.resolve()
            and audit_python.exists()
        ):
            os.execv(str(audit_python), [str(audit_python), *sys.argv])
    if (
        os.environ.get("VLLM_KV_RESIDENCY_USE_SOURCE_TREE") == "1"
        and VLLM_SOURCE
    ):
        source = Path(VLLM_SOURCE).expanduser()
        if source.exists():
            sys.path.insert(0, str(source))


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
    return {
        name: getattr(metrics, name)
        for name in names
        if hasattr(metrics, name)
    }


def artifact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def output_to_record(output: Any, index: int, started: float, ended: float) -> dict[str, Any]:
    generated_tokens = sum(len(item.token_ids) for item in output.outputs)
    finish_reasons = [item.finish_reason for item in output.outputs]
    return {
        "index": index,
        "request_id": output.request_id,
        "finished": output.finished,
        "finish_reasons": finish_reasons,
        "stop_reasons": [item.stop_reason for item in output.outputs],
        "wall_latency_s": ended - started,
        "ttft_s": getattr(output.metrics, "first_token_latency", None)
        if output.metrics is not None
        else None,
        "num_prompt_tokens": len(output.prompt_token_ids or []),
        "num_cached_tokens": output.num_cached_tokens,
        "num_output_tokens": generated_tokens,
        "metrics": metrics_to_record(output.metrics),
        "status": "refused" if "error" in finish_reasons else "served",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--run-id", default="live-scheduler-pressure-hard-exclude")
    parser.add_argument("--max-model-len", type=int, default=768)
    parser.add_argument("--resident-max-tokens", type=int, default=16)
    parser.add_argument("--active-max-tokens", type=int, default=16)
    parser.add_argument("--resident-repeat", type=int, default=52)
    parser.add_argument("--active-repeat", type=int, default=55)
    parser.add_argument("--useful-threshold-blocks", type=int, default=40)
    parser.add_argument("--kv-cache-memory-bytes", type=int, default=24 * 1024 * 1024)
    parser.add_argument("--usable-blocks", type=int, default=68)
    parser.add_argument("--active-timeout-s", type=int, default=5)
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ROOT / "artifacts" / "live_scheduler_pressure" / "telemetry.jsonl",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "artifacts" / "live_scheduler_pressure" / "summary.json",
    )
    return parser.parse_args()


def make_prompts(resident_repeat: int, active_repeat: int) -> tuple[str, str]:
    resident_prompt = (
        "Resident reusable KV claim. Preserve this stable context. "
        * resident_repeat
    ) + "\nResident question: answer with one short sentence."
    active_prompt = (
        "Active live KV pressure request. This text is intentionally distinct. "
        * active_repeat
    ) + "\nActive question: answer with one short sentence."
    return resident_prompt, active_prompt


def main() -> int:
    ensure_audit_runtime()

    from vllm import LLM, SamplingParams

    args = parse_args()
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.jsonl.write_text("")

    os.environ["VLLM_KV_RESIDENCY_TELEMETRY_PATH"] = str(args.jsonl)
    os.environ["VLLM_KV_RESIDENCY_RUN_ID"] = args.run_id
    os.environ["VLLM_KV_RESIDENCY_POLICY"] = "live_scheduler_hard_exclude_pressure"
    os.environ["VLLM_KV_RESIDENCY_USABLE_BLOCKS"] = str(args.usable_blocks)
    os.environ["VLLM_KV_RESIDENCY_CLAIM_REQUEST_IDS"] = "0"
    os.environ["VLLM_KV_RESIDENCY_CLAIM_ID"] = "claim:live-resident"
    os.environ["VLLM_KV_RESIDENCY_PREFIX_ID"] = "live-resident"
    os.environ["VLLM_KV_RESIDENCY_USEFUL_THRESHOLD_BLOCKS"] = str(
        args.useful_threshold_blocks
    )
    os.environ["VLLM_KV_RESIDENCY_PREDICTED_VALUE"] = "1.0"
    os.environ["VLLM_KV_RESIDENCY_CONFIDENCE"] = "1.0"
    os.environ["VLLM_KV_RESIDENCY_PROTECTION_MODE"] = "hard_exclude"
    os.environ["VLLM_KV_RESIDENCY_ENFORCE_PROTECTION"] = "hard_exclude"
    os.environ.pop("VLLM_KV_RESIDENCY_NO_ADMIT_REQUEST_IDS", None)
    os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")

    llm = LLM(
        model=str(args.model),
        trust_remote_code=True,
        dtype="half",
        max_model_len=args.max_model_len,
        enable_prefix_caching=True,
        kv_cache_memory_bytes=args.kv_cache_memory_bytes,
        enforce_eager=True,
        disable_log_stats=False,
    )
    resident_prompt, active_prompt = make_prompts(
        args.resident_repeat, args.active_repeat
    )
    resident_sampling = SamplingParams(
        temperature=0,
        max_tokens=args.resident_max_tokens,
        ignore_eos=True,
    )
    active_sampling = SamplingParams(
        temperature=0,
        max_tokens=args.active_max_tokens,
        ignore_eos=True,
    )

    request_records: list[dict[str, Any]] = []
    started = time.perf_counter()
    resident_output = llm.generate([resident_prompt], resident_sampling, use_tqdm=False)[0]
    ended = time.perf_counter()
    request_records.append(output_to_record(resident_output, 0, started, ended))

    def handle_timeout(_signum: int, _frame: Any) -> None:
        raise GenerateTimeout(
            f"active request did not complete within {args.active_timeout_s}s"
        )

    old_handler = signal.signal(signal.SIGALRM, handle_timeout)
    signal.alarm(args.active_timeout_s)
    try:
        started = time.perf_counter()
        active_output = llm.generate([active_prompt], active_sampling, use_tqdm=False)[0]
        ended = time.perf_counter()
        active_record = output_to_record(active_output, 1, started, ended)
        request_records.append(active_record)
        active_status = active_record["status"]
        active_error = None
    except GenerateTimeout as exc:
        ended = time.perf_counter()
        request_records.append(
            {
                "index": 1,
                "request_id": "1",
                "wall_latency_s": ended - started,
                "ttft_s": None,
                "num_prompt_tokens": None,
                "num_cached_tokens": None,
                "num_output_tokens": 0,
                "metrics": {},
                "status": "timed_out",
            }
        )
        active_status = "timed_out"
        active_error = str(exc)
    except Exception as exc:
        ended = time.perf_counter()
        request_records.append(
            {
                "index": 1,
                "request_id": "1",
                "wall_latency_s": ended - started,
                "ttft_s": None,
                "num_prompt_tokens": None,
                "num_cached_tokens": None,
                "num_output_tokens": 0,
                "metrics": {},
                "status": "error",
            }
        )
        active_status = "error"
        active_error = f"{type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    telemetry_events = [
        json.loads(line) for line in args.jsonl.read_text().splitlines() if line
    ]
    event_counts = {
        event_name: sum(1 for event in telemetry_events if event["event"] == event_name)
        for event_name in sorted({event["event"] for event in telemetry_events})
    }
    claim_events = [
        event
        for event in telemetry_events
        if event["event"].startswith("resident_claim_")
    ]
    active_events = [
        event
        for event in telemetry_events
        if event.get("request_id") == "1"
        or str(event.get("request_id", "")).startswith("1-")
    ]
    active_deferred_events = [
        event for event in active_events if event["event"] == "active_request_deferred"
    ]
    active_refused_events = [
        event for event in active_events if event["event"] == "active_request_refused"
    ]
    resident_materialized = [
        event
        for event in telemetry_events
        if event["event"] == "resident_block_materialized"
        and event.get("is_protected_resident") is True
    ]

    summary = {
        "status": "ok" if active_status == "served" else "active_not_served",
        "run_id": args.run_id,
        "model": str(args.model),
        "scheduler_path": "vllm.LLM.generate",
        "server_flags": {
            "enable_prefix_caching": True,
            "max_model_len": args.max_model_len,
            "resident_max_tokens": args.resident_max_tokens,
            "active_max_tokens": args.active_max_tokens,
            "dtype": "half",
            "enforce_eager": True,
            "disable_log_stats": False,
            "kv_cache_memory_bytes": args.kv_cache_memory_bytes,
            "usable_blocks": args.usable_blocks,
            "active_timeout_s": args.active_timeout_s,
            "useful_threshold_blocks": args.useful_threshold_blocks,
        },
        "requests": request_records,
        "active_status": active_status,
        "active_error": active_error,
        "protected_resident_materialized_events": len(resident_materialized),
        "claim_lifecycle_event_counts": {
            event_name: sum(1 for event in claim_events if event["event"] == event_name)
            for event_name in sorted({event["event"] for event in claim_events})
        },
        "active_event_counts": {
            event_name: sum(1 for event in active_events if event["event"] == event_name)
            for event_name in sorted({event["event"] for event in active_events})
        },
        "first_active_deferred_event": (
            active_deferred_events[0] if active_deferred_events else None
        ),
        "first_active_refused_event": (
            active_refused_events[0] if active_refused_events else None
        ),
        "blocking_claim_ids": sorted(
            {
                claim_id
                for event in active_deferred_events + active_refused_events
                for claim_id in event.get("blocking_claim_ids", [])
            }
        ),
        "telemetry_events": len(telemetry_events),
        "telemetry_event_counts": event_counts,
        "jsonl": artifact_path(args.jsonl),
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
