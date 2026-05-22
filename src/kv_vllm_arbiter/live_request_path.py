"""Request-path coupled ResidentClaim offload lifecycle instrumentation.

This module deliberately does not claim native vLLM offload support. It adapts
actual vLLM request ids and request timing records into the existing reference
offload lifecycle/outcome hook, so a live run can distinguish request-coupled
reference instrumentation from generic transfer counters.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from kv_vllm_arbiter.offload_lifecycle import (
    Event,
    OffloadLifecycleConfig,
    build_generic_substrate_trace,
    build_reference_trace,
    evaluate_offload_lifecycle_events,
)


INSTRUMENTATION_SCOPE = "request_path_coupled_reference_not_native_vllm_offload"

CONTRACT_EVENT_ALIASES = {
    "resident_claim_accepted": "claim_accepted",
    "resident_claim_materialized": "predicate_materialized",
    "resident_claim_offloaded": "claim_offloaded",
    "resident_claim_restore_required": "restore_required_for_reuse",
    "resident_claim_restored": "claim_restored_before_reuse",
    "resident_claim_reuse_after_restore": "reuse_consumed_restored_state",
    "resident_claim_restoration_failed": "restoration_failed",
    "active_request_refused": "active_request_refused",
}


@dataclass(frozen=True)
class LiveRequestRecord:
    role: str
    request_id: str
    wall_latency_s: float | None = None
    ttft_s: float | None = None
    num_prompt_tokens: int | None = None
    num_cached_tokens: int | None = None
    num_output_tokens: int | None = None
    status: str = "served"

    @classmethod
    def from_mapping(cls, record: dict[str, Any]) -> "LiveRequestRecord":
        return cls(
            role=str(record["role"]),
            request_id=str(record["request_id"]),
            wall_latency_s=_optional_float(record.get("wall_latency_s")),
            ttft_s=_optional_float(record.get("ttft_s")),
            num_prompt_tokens=_optional_int(record.get("num_prompt_tokens")),
            num_cached_tokens=_optional_int(record.get("num_cached_tokens")),
            num_output_tokens=_optional_int(record.get("num_output_tokens")),
            status=str(record.get("status", "served")),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "request_id": self.request_id,
            "wall_latency_s": self.wall_latency_s,
            "ttft_s": self.ttft_s,
            "num_prompt_tokens": self.num_prompt_tokens,
            "num_cached_tokens": self.num_cached_tokens,
            "num_output_tokens": self.num_output_tokens,
            "status": self.status,
        }


def build_request_coupled_trace(
    request_records: Iterable[LiveRequestRecord | dict[str, Any]],
    *,
    run_id: str,
    emit_events: bool,
    scenario: str = "positive_bundle",
    claim_id: str = "claim:live-request-path",
) -> list[Event]:
    """Build a lifecycle trace tied to live request ids.

    The positive trace uses the existing reference lifecycle checker, but all
    request-bearing events are bound to request ids observed from the live
    request path. The returned events carry `instrumentation_scope` so they
    cannot be confused with native vLLM offload telemetry.
    """

    records = _normalize_records(request_records)
    if scenario == "generic_substrate":
        config = _config_from_records(records, run_id=run_id, claim_id=claim_id)
        events = build_generic_substrate_trace(config)
        return _annotate_events(events, records)

    config = _config_from_records(records, run_id=run_id, claim_id=claim_id)
    events = build_reference_trace(scenario, config=config, emit_events=emit_events)
    return _annotate_events(events, records)


def evaluate_request_coupled_trace(events: Iterable[Event]) -> dict[str, Any]:
    """Evaluate lifecycle semantics and expose the live contract order."""

    event_list = list(events)
    evaluation = evaluate_offload_lifecycle_events(event_list)
    return {
        "passes_reference_gate": evaluation.passes_reference_gate,
        "gate_summary": evaluation.gate_summary,
        "event_counts": evaluation.event_counts,
        "active_claim_count": evaluation.active_claim_count,
        "claim_registry_size": evaluation.claim_registry_size,
        "contract_event_order": [
            event["contract_event"]
            for event in sorted(event_list, key=lambda item: item.get("event_sequence", 0))
            if event.get("contract_event")
        ],
        "instrumentation_scope": INSTRUMENTATION_SCOPE,
    }


def request_metrics(records: Iterable[LiveRequestRecord]) -> dict[str, Any]:
    record_list = list(records)
    latencies = [
        record.wall_latency_s
        for record in record_list
        if record.wall_latency_s is not None
    ]
    ttfts = [record.ttft_s for record in record_list if record.ttft_s is not None]
    return {
        "request_count": len(record_list),
        "served_request_count": sum(1 for record in record_list if record.status == "served"),
        "latency_s_sum": round(sum(latencies), 6) if latencies else None,
        "latency_s_mean": round(sum(latencies) / len(latencies), 6)
        if latencies
        else None,
        "ttft_s_mean": round(sum(ttfts) / len(ttfts), 6) if ttfts else None,
        "output_tokens": sum(
            record.num_output_tokens or 0
            for record in record_list
            if record.num_output_tokens is not None
        ),
        "cached_tokens_after_first_request": [
            record.num_cached_tokens
            for record in record_list[1:]
            if record.num_cached_tokens
        ],
    }


def _normalize_records(
    request_records: Iterable[LiveRequestRecord | dict[str, Any]],
) -> list[LiveRequestRecord]:
    records = [
        record if isinstance(record, LiveRequestRecord) else LiveRequestRecord.from_mapping(record)
        for record in request_records
    ]
    roles = {record.role for record in records}
    missing = {"resident", "reuse", "failure"} - roles
    if missing:
        raise ValueError(f"missing request role(s): {', '.join(sorted(missing))}")
    return records


def _config_from_records(
    records: list[LiveRequestRecord],
    *,
    run_id: str,
    claim_id: str,
) -> OffloadLifecycleConfig:
    by_role = {record.role: record for record in records}
    resident = by_role["resident"]
    reuse = by_role["reuse"]
    failure = by_role["failure"]
    prompt_tokens = resident.num_prompt_tokens or 128
    block_count = max(1, min(16, (prompt_tokens + 15) // 16))
    token_map_digest = hashlib.sha256(
        "|".join(record.request_id for record in records).encode("utf-8")
    ).hexdigest()[:16]
    return OffloadLifecycleConfig(
        run_id=run_id,
        policy="request_path_coupled_reference_hook",
        claim_id=claim_id,
        request_id=resident.request_id,
        reuse_request_id=reuse.request_id,
        failure_request_id=failure.request_id,
        prefix_id=f"prefix:{resident.request_id}",
        reusable_object_id=f"vllm-request-prefix:{resident.request_id}",
        predicate_id=f"predicate:live-leading-prefix-{block_count}",
        materialization_predicate=f"leading_prefix_at_least({block_count})",
        request_token_map_id=f"token-map:live:{token_map_digest}",
        cache_identity="vllm-live-request-path-cache:v1",
        block_count=block_count,
    )


def _annotate_events(events: list[Event], records: list[LiveRequestRecord]) -> list[Event]:
    by_request_id = {record.request_id: record for record in records}
    annotated: list[Event] = []
    for event in events:
        record = dict(event)
        request_record = by_request_id.get(str(record.get("request_id")))
        record["instrumentation_scope"] = INSTRUMENTATION_SCOPE
        record["native_vllm_offload_claimed"] = False
        record["request_path_coupled_reference"] = True
        record["contract_event"] = CONTRACT_EVENT_ALIASES.get(str(record.get("event")))
        if record.get("event") == "resident_claim_restoration_failed":
            record["contract_event_detail"] = "restoration_unavailable_injected"
        if request_record is not None:
            record["live_request_role"] = request_record.role
            record["live_request_wall_latency_s"] = request_record.wall_latency_s
            record["live_request_ttft_s"] = request_record.ttft_s
            record["live_request_num_prompt_tokens"] = request_record.num_prompt_tokens
            record["live_request_num_cached_tokens"] = request_record.num_cached_tokens
        annotated.append(record)
    return annotated


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
