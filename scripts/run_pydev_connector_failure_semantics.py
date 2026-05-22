#!/usr/bin/env python3
"""Run patched pydev vLLM OffloadingConnector failure-semantics scenarios."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kv_vllm_arbiter.offload_lifecycle import write_jsonl  # noqa: E402
from kv_vllm_arbiter.pydev_connector_failure import (  # noqa: E402
    evaluate_pydev_connector_events,
    load_jsonl,
    write_json,
)


DEFAULT_MODEL = os.environ.get(
    "VLLM_KV_RESIDENCY_MODEL",
    "HuggingFaceTB/SmolLM2-135M-Instruct",
)
DEFAULT_OUT_DIR = ROOT / "artifacts" / "pydev_connector_failure_semantics"
DEFAULT_VLLM_SOURCE = Path(
    os.environ.get("VLLM_KV_RESIDENCY_VLLM_SOURCE", "/home/krooksn/ai/runtimes/vllm/repo")
)
SHARED_PREFIX = (
    "Resident KV request-path prefix. Preserve this stable context. "
    "The repeated text is intentionally shared for prefix-cache observation. "
    * 18
)


@dataclass(frozen=True)
class Scenario:
    name: str
    claim_params: bool
    event_path: bool
    inject_failure: bool = False
    failure_target: str | None = None
    allow_unclaimed_failure: bool = False
    kv_load_failure_policy: str = "fail"
    synthetic_generic: bool = False


SCENARIOS = {
    "success_no_event_path": Scenario(
        name="success_no_event_path",
        claim_params=False,
        event_path=False,
    ),
    "success_path": Scenario(
        name="success_path",
        claim_params=True,
        event_path=True,
    ),
    "claimed_load_failure": Scenario(
        name="claimed_load_failure",
        claim_params=True,
        event_path=True,
        inject_failure=True,
        failure_target="same_claim",
    ),
    "wrong_claim_failure": Scenario(
        name="wrong_claim_failure",
        claim_params=True,
        event_path=True,
        inject_failure=True,
        failure_target="wrong_claim",
    ),
    "unclaimed_load_failure": Scenario(
        name="unclaimed_load_failure",
        claim_params=False,
        event_path=True,
        inject_failure=True,
        allow_unclaimed_failure=True,
    ),
    "fallback_recompute": Scenario(
        name="fallback_recompute",
        claim_params=True,
        event_path=True,
        inject_failure=True,
        failure_target="same_claim",
        kv_load_failure_policy="recompute",
    ),
    "generic_counter_only": Scenario(
        name="generic_counter_only",
        claim_params=False,
        event_path=True,
        synthetic_generic=True,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-model-len", type=int, default=512)
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.35)
    parser.add_argument("--kv-cache-memory-bytes", type=int, default=None)
    parser.add_argument("--vllm-source", type=Path, default=DEFAULT_VLLM_SOURCE)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def maybe_add_vllm_source(path: Path) -> None:
    if path.exists():
        sys.path.insert(0, str(path))


def import_runtime() -> tuple[Any, Any]:
    from vllm import LLM, SamplingParams

    return LLM, SamplingParams


def runtime_payload() -> dict[str, Any]:
    import torch
    import vllm

    return {
        "vllm_version": getattr(vllm, "__version__", None),
        "vllm_file": inspect.getfile(vllm),
        "torch_version": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count(),
        "device0": torch.cuda.get_device_name(0)
        if torch.cuda.is_available()
        else None,
    }


def claim_id(run_id: str) -> str:
    return f"{run_id}:claim:live-request-path"


def prompts() -> dict[str, str]:
    return {
        "resident": SHARED_PREFIX + "\nResident turn: answer with a short sentence.",
        "reuse": SHARED_PREFIX + "\nReuse turn: answer with a different short sentence.",
    }


def resident_claim_params(role: str, run_id: str) -> dict[str, Any]:
    digest = hashlib.sha256(SHARED_PREFIX.encode("utf-8")).hexdigest()[:16]
    return {
        "resident_claim": True,
        "resident_claim_id": claim_id(run_id),
        "resident_claim_role": role,
        "predicate_id": "predicate:live-leading-prefix",
        "materialization_predicate": "leading_prefix_at_least(1)",
        "prefix_id": f"prefix:shared:{digest}",
        "reusable_object_id": f"vllm-request-prefix:{digest}",
        "cache_identity": "vllm-live-request-path-cache:v1",
        "request_token_map_id": f"token-map:shared-prefix:{digest}",
        "instrumentation_scope": (
            "native_vllm_offloading_connector_failure_probe_not_conformance"
        ),
    }


def sampling_params(
    SamplingParams: Any,
    *,
    role: str,
    prompt: str,
    args: argparse.Namespace,
    scenario: Scenario,
    run_id: str,
) -> Any:
    extra_args = None
    if scenario.claim_params:
        extra_args = {
            "kv_transfer_params": resident_claim_params(role, run_id),
        }
    return SamplingParams(
        temperature=0,
        max_tokens=args.max_tokens,
        ignore_eos=True,
        extra_args=extra_args,
    )


def configure_env(scenario: Scenario, event_path: Path, run_id: str) -> None:
    os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"] = "0"
    os.environ["VLLM_RESIDENT_CLAIM_HOOK_SCOPE"] = (
        f"pydev_offloading_connector_failure_semantics:{scenario.name}"
    )
    for key in (
        "VLLM_RESIDENT_CLAIM_EVENT_PATH",
        "VLLM_RESIDENT_CLAIM_INJECT_LOAD_FAILURE",
        "VLLM_RESIDENT_CLAIM_FAILURE_CLAIM_ID",
        "VLLM_RESIDENT_CLAIM_FAILURE_ALLOW_UNCLAIMED",
        "VLLM_RESIDENT_CLAIM_FAILURE_MODE",
        "VLLM_RESIDENT_CLAIM_FAILURE_REASON",
    ):
        os.environ.pop(key, None)
    if scenario.event_path:
        os.environ["VLLM_RESIDENT_CLAIM_EVENT_PATH"] = str(event_path)
    if scenario.inject_failure:
        os.environ["VLLM_RESIDENT_CLAIM_INJECT_LOAD_FAILURE"] = "1"
        os.environ["VLLM_RESIDENT_CLAIM_FAILURE_MODE"] = "refusal"
        os.environ["VLLM_RESIDENT_CLAIM_FAILURE_REASON"] = (
            "controlled_resident_claim_cpu_to_gpu_load_failure"
        )
        if scenario.failure_target == "same_claim":
            os.environ["VLLM_RESIDENT_CLAIM_FAILURE_CLAIM_ID"] = claim_id(run_id)
        elif scenario.failure_target == "wrong_claim":
            os.environ["VLLM_RESIDENT_CLAIM_FAILURE_CLAIM_ID"] = (
                f"{claim_id(run_id)}:wrong"
            )
        if scenario.allow_unclaimed_failure:
            os.environ["VLLM_RESIDENT_CLAIM_FAILURE_ALLOW_UNCLAIMED"] = "1"


def kv_transfer_config(scenario: Scenario) -> dict[str, Any]:
    return {
        "kv_connector": "OffloadingConnector",
        "kv_role": "kv_both",
        "kv_load_failure_policy": scenario.kv_load_failure_policy,
        "kv_connector_extra_config": {
            "block_size": 64,
            "cpu_bytes_to_use": 536870912,
            "store_threshold": 1,
        },
    }


def run_one_request(
    llm: Any,
    SamplingParams: Any,
    *,
    role: str,
    prompt: str,
    args: argparse.Namespace,
    scenario: Scenario,
    run_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        output = llm.generate(
            [prompt],
            sampling_params(
                SamplingParams,
                role=role,
                prompt=prompt,
                args=args,
                scenario=scenario,
                run_id=run_id,
            ),
            use_tqdm=False,
        )[0]
        ended = time.perf_counter()
        generated_tokens = sum(len(item.token_ids) for item in output.outputs)
        return {
            "role": role,
            "request_id": output.request_id,
            "status": "served",
            "wall_latency_s": round(ended - started, 6),
            "ttft_s": getattr(output.metrics, "first_token_latency", None)
            if output.metrics is not None
            else None,
            "num_prompt_tokens": len(output.prompt_token_ids or []),
            "num_cached_tokens": output.num_cached_tokens,
            "num_output_tokens": generated_tokens,
            "exception": None,
        }
    except Exception as exc:
        ended = time.perf_counter()
        return {
            "role": role,
            "request_id": None,
            "status": "exception",
            "wall_latency_s": round(ended - started, 6),
            "ttft_s": None,
            "num_prompt_tokens": None,
            "num_cached_tokens": None,
            "num_output_tokens": 0,
            "exception": f"{type(exc).__name__}: {exc}",
        }


def run_vllm_scenario(
    args: argparse.Namespace,
    scenario: Scenario,
    event_path: Path,
    run_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    maybe_add_vllm_source(args.vllm_source)
    LLM, SamplingParams = import_runtime()
    llm_kwargs: dict[str, Any] = {
        "model": str(args.model),
        "trust_remote_code": True,
        "dtype": "half",
        "max_model_len": args.max_model_len,
        "enable_prefix_caching": True,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "enforce_eager": True,
        "disable_log_stats": True,
        "kv_transfer_config": kv_transfer_config(scenario),
    }
    if args.kv_cache_memory_bytes is not None:
        llm_kwargs["kv_cache_memory_bytes"] = args.kv_cache_memory_bytes

    llm = LLM(**llm_kwargs)
    prompt_map = prompts()
    records = [
        run_one_request(
            llm,
            SamplingParams,
            role="resident",
            prompt=prompt_map["resident"],
            args=args,
            scenario=scenario,
            run_id=run_id,
        )
    ]
    if records[0]["status"] == "served":
        llm.reset_prefix_cache(reset_running_requests=False, reset_connector=False)
        records.append(
            run_one_request(
                llm,
                SamplingParams,
                role="reuse",
                prompt=prompt_map["reuse"],
                args=args,
                scenario=scenario,
                run_id=run_id,
            )
        )
    return records, runtime_payload()


def synthetic_generic_events(run_id: str) -> list[dict[str, Any]]:
    now = time.time_ns()
    return [
        {
            "event": "generic_kv_transfer_failed_counter",
            "event_sequence": 1,
            "timestamp_ns": now,
            "run_id": run_id,
            "transfer_type": ["CPU", "GPU"],
            "failure_count": 1,
        },
        {
            "event": "generic_request_error_counter",
            "event_sequence": 2,
            "timestamp_ns": now + 1,
            "run_id": run_id,
            "request_failures": 1,
        },
    ]


def transfer_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    transfers = [
        event
        for event in events
        if event.get("event") == "offload_worker_transfer_finished"
    ]
    return {
        "worker_transfer_count": len(transfers),
        "worker_transfer_sizes": [
            event.get("transfer_size")
            for event in transfers
            if event.get("transfer_size") is not None
        ],
        "worker_transfer_times_s": [
            event.get("transfer_time")
            for event in transfers
            if event.get("transfer_time") is not None
        ],
        "directions": [event.get("transfer_type") for event in transfers],
    }


def load_failure_to_outcome_latency_ns(events: list[dict[str, Any]]) -> int | None:
    failure = next(
        (
            event
            for event in events
            if event.get("event") == "resident_claim_restoration_failed"
        ),
        None,
    )
    refusal = next(
        (event for event in events if event.get("event") == "active_request_refused"),
        None,
    )
    if failure is None or refusal is None:
        return None
    if "monotonic_ns" not in failure or "monotonic_ns" not in refusal:
        return None
    return int(refusal["monotonic_ns"]) - int(failure["monotonic_ns"])


def render_markdown(payload: dict[str, Any]) -> str:
    evaluation = payload["evaluation"]["gate_summary"]
    lines = [
        f"# Pydev Connector Failure Semantics: {payload['scenario']}",
        "",
        payload["claim_boundary"],
        "",
        f"Status: `{payload['status']}`",
        "",
        f"Observation gate: `{'pass' if payload['evaluation']['connector_observation_success'] else 'fail'}`",
        "",
        f"Failure-outcome gate: `{'pass' if payload['evaluation']['restoration_failure_outcome_success'] else 'fail'}`",
        "",
        f"Observation missing: `{', '.join(evaluation['observation_missing_requirements']) or '-'}`",
        "",
        f"Failure missing: `{', '.join(evaluation['failure_missing_requirements']) or '-'}`",
        "",
        "| Role | Status | Latency s | Cached tokens | Output tokens | Exception |",
        "|---|---|---:|---:|---:|---|",
    ]
    for record in payload["request_records"]:
        lines.append(
            "| "
            f"{record['role']} | {record['status']} | "
            f"{record['wall_latency_s']} | {record['num_cached_tokens']} | "
            f"{record['num_output_tokens']} | {record['exception'] or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def annotate_request_records(
    records: list[dict[str, Any]],
    evaluation_record: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence = evaluation_record["gate_summary"]["ordered_evidence"]
    controls = evaluation_record["gate_summary"]["controls"]
    refused = evidence.get("refusal") is not None
    restoration_failed = evidence.get("restoration_failed") is not None
    generic_failed = (
        evidence.get("load_failed") is not None and not restoration_failed
    ) or bool(controls.get("unclaimed_failure_rejected"))
    annotated = [dict(record) for record in records]
    for record in annotated:
        if record.get("role") != "reuse":
            continue
        if refused:
            record["status"] = "controlled_refused"
            record["connector_outcome"] = "active_request_refused"
        elif restoration_failed and record.get("status") == "served":
            record["status"] = "served_after_failed_load_recompute"
            record["connector_outcome"] = "fallback_recompute_not_claim_satisfaction"
        elif generic_failed:
            record["status"] = "generic_connector_load_failed"
            record["connector_outcome"] = "not_claim_scoped"
    return annotated


def main() -> int:
    args = parse_args()
    scenario = SCENARIOS[args.scenario]
    run_id = args.run_id or f"pydev-connector-failure:{scenario.name}"
    scenario_dir = args.out_dir / scenario.name
    scenario_dir.mkdir(parents=True, exist_ok=True)
    event_path = scenario_dir / "vllm_runtime_events.jsonl"
    if event_path.exists():
        event_path.unlink()

    configure_env(scenario, event_path, run_id)
    runtime = {}
    request_records: list[dict[str, Any]] = []
    status = "ok"
    if scenario.synthetic_generic:
        events = synthetic_generic_events(run_id)
        write_jsonl(event_path, events)
    else:
        try:
            request_records, runtime = run_vllm_scenario(
                args,
                scenario,
                event_path,
                run_id,
            )
        except Exception as exc:
            status = "harness_exception"
            request_records = [
                {
                    "role": "harness",
                    "request_id": None,
                    "status": "exception",
                    "wall_latency_s": None,
                    "ttft_s": None,
                    "num_prompt_tokens": None,
                    "num_cached_tokens": None,
                    "num_output_tokens": 0,
                    "exception": f"{type(exc).__name__}: {exc}",
                }
            ]
        events = load_jsonl(event_path)

    expected_claim = claim_id(run_id) if scenario.claim_params else None
    evaluation = evaluate_pydev_connector_events(
        events,
        expected_claim_id=expected_claim,
    )
    evaluation_record = evaluation.to_record()
    request_records = annotate_request_records(request_records, evaluation_record)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "scenario": scenario.name,
        "run_id": run_id,
        "model": str(args.model),
        "python": sys.executable,
        "runtime": runtime,
        "connector_config": kv_transfer_config(scenario),
        "scenario_config": {
            "claim_params": scenario.claim_params,
            "event_path": scenario.event_path,
            "inject_failure": scenario.inject_failure,
            "failure_target": scenario.failure_target,
            "allow_unclaimed_failure": scenario.allow_unclaimed_failure,
            "kv_load_failure_policy": scenario.kv_load_failure_policy,
            "synthetic_generic": scenario.synthetic_generic,
        },
        "event_path": str(event_path.resolve()),
        "event_count": len(events),
        "event_bytes": event_path.stat().st_size if event_path.exists() else 0,
        "request_records": request_records,
        "evaluation": evaluation_record,
        "transfer_metrics": transfer_metrics(events),
        "load_failure_to_outcome_latency_ns": load_failure_to_outcome_latency_ns(
            events
        ),
        "disable_log_stats_required": True,
        "ttft_note": "TTFT is unavailable when vLLM returns no metrics under disable_log_stats=True.",
        "claim_boundary": (
            "Local patched pydev vLLM OffloadingConnector mechanism only; "
            "not upstream ResidentClaim support and not production offload performance."
        ),
    }
    write_json(scenario_dir / "summary.json", payload)
    (scenario_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
