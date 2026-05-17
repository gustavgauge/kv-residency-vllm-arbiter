#!/usr/bin/env python3
"""Run a full vLLM LLM.generate scheduler path with request-level metrics."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PYTHON = os.environ.get("VLLM_AUDIT_PYTHON")
DEFAULT_MODEL = os.environ.get(
    "VLLM_KV_RESIDENCY_MODEL", "HuggingFaceTB/SmolLM2-135M-Instruct"
)


def ensure_audit_runtime() -> None:
    if not AUDIT_PYTHON:
        return
    audit_python = Path(AUDIT_PYTHON).expanduser()
    if Path(sys.executable).resolve() != audit_python.resolve() and audit_python.exists():
        os.execv(str(audit_python), [str(audit_python), *sys.argv])


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--run-id", default="live-scheduler-smollm-prefix-cache")
    parser.add_argument("--max-model-len", type=int, default=512)
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--num-prompts", type=int, default=3)
    parser.add_argument("--kv-cache-memory-bytes", type=int, default=None)
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=ROOT / "artifacts" / "live_scheduler" / "telemetry.jsonl",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "artifacts" / "live_scheduler" / "summary.json",
    )
    return parser.parse_args()


def main() -> int:
    ensure_audit_runtime()

    from vllm import LLM, SamplingParams

    args = parse_args()
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.jsonl.write_text("")

    os.environ["VLLM_KV_RESIDENCY_TELEMETRY_PATH"] = str(args.jsonl)
    os.environ["VLLM_KV_RESIDENCY_RUN_ID"] = args.run_id
    os.environ["VLLM_KV_RESIDENCY_POLICY"] = "live_scheduler_native"
    os.environ.pop("VLLM_KV_RESIDENCY_NO_ADMIT_REQUEST_IDS", None)
    os.environ.pop("VLLM_KV_RESIDENCY_CLAIM_REQUEST_IDS", None)
    os.environ.pop("VLLM_KV_RESIDENCY_ENFORCE_PROTECTION", None)
    os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")

    stable_prefix = (
        "You are evaluating prefix cache reuse. "
        "Repeat this stable context exactly. " * 36
    )
    prompts = [
        stable_prefix + f"\nQuestion {idx}: answer with one short sentence."
        for idx in range(args.num_prompts)
    ]

    llm_kwargs: dict[str, Any] = {
        "model": str(args.model),
        "trust_remote_code": True,
        "dtype": "half",
        "max_model_len": args.max_model_len,
        "enable_prefix_caching": True,
        "gpu_memory_utilization": 0.35,
        "enforce_eager": True,
        "disable_log_stats": False,
    }
    if args.kv_cache_memory_bytes is not None:
        llm_kwargs["kv_cache_memory_bytes"] = args.kv_cache_memory_bytes

    llm = LLM(**llm_kwargs)
    sampling = SamplingParams(
        temperature=0,
        max_tokens=args.max_tokens,
        ignore_eos=True,
    )

    request_records = []
    for index, prompt in enumerate(prompts):
        started = time.perf_counter()
        outputs = llm.generate([prompt], sampling, use_tqdm=False)
        ended = time.perf_counter()
        output = outputs[0]
        generated_tokens = sum(len(item.token_ids) for item in output.outputs)
        request_records.append(
            {
                "index": index,
                "request_id": output.request_id,
                "wall_latency_s": ended - started,
                "ttft_s": getattr(output.metrics, "first_token_latency", None)
                if output.metrics is not None
                else None,
                "num_prompt_tokens": len(output.prompt_token_ids or []),
                "num_cached_tokens": output.num_cached_tokens,
                "num_output_tokens": generated_tokens,
                "metrics": metrics_to_record(output.metrics),
            }
        )

    telemetry_events = [
        json.loads(line) for line in args.jsonl.read_text().splitlines() if line
    ]
    summary = {
        "status": "ok",
        "run_id": args.run_id,
        "model": str(args.model),
        "scheduler_path": "vllm.LLM.generate",
        "server_flags": {
            "enable_prefix_caching": True,
            "max_model_len": args.max_model_len,
            "max_tokens": args.max_tokens,
            "dtype": "half",
            "enforce_eager": True,
            "disable_log_stats": False,
            "gpu_memory_utilization": 0.35,
            "kv_cache_memory_bytes": args.kv_cache_memory_bytes,
        },
        "requests": request_records,
        "observed_cached_tokens_after_first_request": [
            record["num_cached_tokens"]
            for record in request_records[1:]
            if record["num_cached_tokens"]
        ],
        "telemetry_events": len(telemetry_events),
        "telemetry_event_counts": {
            event_name: sum(1 for event in telemetry_events if event["event"] == event_name)
            for event_name in sorted({event["event"] for event in telemetry_events})
        },
        "jsonl": artifact_path(args.jsonl),
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
