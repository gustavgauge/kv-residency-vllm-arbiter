"""Evaluate patched pydev vLLM OffloadingConnector failure semantics."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


Event = dict[str, Any]


@dataclass(frozen=True)
class PydevConnectorEvaluation:
    gate_summary: dict[str, Any]
    event_counts: dict[str, int]
    analyzer_runtime_ns: int

    @property
    def connector_observation_success(self) -> bool:
        return not self.gate_summary["observation_missing_requirements"]

    @property
    def restoration_failure_outcome_success(self) -> bool:
        return not self.gate_summary["failure_missing_requirements"]

    def to_record(self) -> dict[str, Any]:
        return {
            "gate_summary": self.gate_summary,
            "event_counts": self.event_counts,
            "analyzer_runtime_ns": self.analyzer_runtime_ns,
            "connector_observation_success": self.connector_observation_success,
            "restoration_failure_outcome_success": (
                self.restoration_failure_outcome_success
            ),
        }


def load_jsonl(path: Path) -> list[Event]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def evaluate_pydev_connector_events(
    events: Iterable[Event],
    *,
    expected_claim_id: str | None = None,
) -> PydevConnectorEvaluation:
    start = time.perf_counter_ns()
    event_list = sorted((dict(event) for event in events), key=_event_order)
    counts = event_counts(event_list)
    claim_id = expected_claim_id or _first_claim_id(event_list)
    claim_events = [
        event
        for event in event_list
        if claim_id is not None and _event_claim_id(event) == claim_id
    ]

    request_initialized = _first_event(claim_events, "request_initialized")
    store_created = _first_event(claim_events, "offload_store_job_created")
    store_transfer = _first_transfer(
        claim_events,
        ("GPU", "CPU"),
        success=True,
        after=store_created,
    )
    store_completed = _first_event_after(
        claim_events,
        "offload_job_completed",
        store_transfer,
        predicate=lambda event: bool(event.get("is_store")),
    )
    lookup_hit = _first_event(
        claim_events,
        "offload_lookup_result",
        predicate=lambda event: int(event.get("num_hit_tokens") or 0) > 0
        and bool(event.get("will_load_async")),
    )
    restore_required = _first_event_after(
        claim_events,
        "resident_claim_restore_required",
        lookup_hit,
    )
    load_created = _first_event_after(
        claim_events,
        "offload_load_job_created",
        restore_required,
    )
    load_transfer_success = _first_transfer(
        claim_events,
        ("CPU", "GPU"),
        success=True,
        after=load_created,
    )
    load_completed = _first_event_after(
        claim_events,
        "offload_job_completed",
        load_transfer_success,
        predicate=lambda event: not bool(event.get("is_store")),
    )
    restored = _first_event_after(
        claim_events,
        "resident_claim_restored",
        load_transfer_success,
    )

    failed_transfer = _first_transfer(
        claim_events,
        ("CPU", "GPU"),
        success=False,
        after=load_created,
    )
    load_failed = _first_event_after(
        claim_events,
        "offload_load_job_failed",
        failed_transfer,
        predicate=lambda event: not bool(event.get("is_store")),
    )
    restoration_failed = _first_event_after(
        claim_events,
        "resident_claim_restoration_failed",
        load_failed,
        predicate=lambda event: event.get("outcome_claim_id") == claim_id
        and bool(event.get("controlled_restoration_unavailable"))
        and bool(event.get("failure_injection_flag")),
    )
    refusal = _first_event_after(
        claim_events,
        "active_request_refused",
        restoration_failed,
        predicate=lambda event: event.get("outcome_claim_id") == claim_id
        and claim_id in event.get("blocking_claim_ids", []),
    )

    generic_failed_load = _first_event(event_list, "offload_load_job_failed")
    unclaimed_failure = generic_failed_load is not None and not _event_claim_id(
        generic_failed_load
    )
    wrong_claim_rejected = failed_transfer is None and restoration_failed is None
    fallback_recompute_rejected = (
        restoration_failed is not None
        and refusal is None
        and restoration_failed.get("claim_scoped_outcome_type") != "refusal"
    )
    fallback_satisfied_after_failure = _first_event_after(
        claim_events,
        "resident_claim_restored",
        restoration_failed,
    )

    observation_missing = []
    if request_initialized is None:
        observation_missing.append("claim_metadata_before_lifecycle")
    if store_created is None or store_transfer is None or store_completed is None:
        observation_missing.append("store_offload_to_cpu_path")
    if lookup_hit is None or load_created is None:
        observation_missing.append("reuse_lookup_hit_requiring_load")
    if load_transfer_success is None or load_completed is None or restored is None:
        observation_missing.append("cpu_to_gpu_restore_success")
    if request_initialized and store_created and not (
        _event_order(request_initialized) < _event_order(store_created)
    ):
        observation_missing.append("claim_metadata_ordering")

    failure_missing = []
    if request_initialized is None:
        failure_missing.append("claim_metadata_before_lifecycle")
    if store_created is None or store_transfer is None:
        failure_missing.append("store_offload_to_cpu_path")
    if lookup_hit is None or restore_required is None or load_created is None:
        failure_missing.append("restore_required_before_failure")
    if failed_transfer is None or load_failed is None:
        failure_missing.append("controlled_cpu_to_gpu_load_failure")
    if restoration_failed is None:
        failure_missing.append("claim_scoped_restoration_failed")
    if refusal is None:
        failure_missing.append("fail_closed_active_request_refused")
    if fallback_satisfied_after_failure is not None:
        failure_missing.append("fallback_recompute_counted_as_satisfaction")

    ordered_failure = _ordered(
        request_initialized,
        store_created,
        store_transfer,
        lookup_hit,
        restore_required,
        load_created,
        failed_transfer,
        load_failed,
        restoration_failed,
        refusal,
    )
    if failure_missing == [] and not ordered_failure:
        failure_missing.append("ordered_failure_semantics")

    summary = {
        "schema_version": 1,
        "claim_id": claim_id,
        "observation_missing_requirements": sorted(set(observation_missing)),
        "failure_missing_requirements": sorted(set(failure_missing)),
        "controls": {
            "generic_counter_only_rejected": not claim_id,
            "wrong_claim_failure_rejected": wrong_claim_rejected,
            "unclaimed_failure_rejected": unclaimed_failure and restoration_failed is None,
            "fallback_recompute_rejected": fallback_recompute_rejected,
            "fallback_recompute_counted_as_satisfaction": (
                fallback_satisfied_after_failure is not None
            ),
        },
        "ordered_evidence": {
            "request_initialized": _compact(request_initialized),
            "store_created": _compact(store_created),
            "store_transfer": _compact(store_transfer),
            "store_completed": _compact(store_completed),
            "lookup_hit": _compact(lookup_hit),
            "restore_required": _compact(restore_required),
            "load_created": _compact(load_created),
            "load_transfer_success": _compact(load_transfer_success),
            "load_completed": _compact(load_completed),
            "restored": _compact(restored),
            "failed_transfer": _compact(failed_transfer),
            "load_failed": _compact(load_failed),
            "restoration_failed": _compact(restoration_failed),
            "refusal": _compact(refusal),
        },
        "claim_boundary": (
            "Patched pydev vLLM OffloadingConnector evidence only; this is not "
            "native upstream ResidentClaim support or production offload performance."
        ),
    }
    analyzer_runtime_ns = time.perf_counter_ns() - start
    return PydevConnectorEvaluation(
        gate_summary=summary,
        event_counts=counts,
        analyzer_runtime_ns=analyzer_runtime_ns,
    )


def event_counts(events: Iterable[Event]) -> dict[str, int]:
    event_list = list(events)
    return {
        event_name: sum(1 for event in event_list if event.get("event") == event_name)
        for event_name in sorted({str(event.get("event")) for event in event_list})
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _first_claim_id(events: list[Event]) -> str | None:
    for event in events:
        claim_id = _event_claim_id(event)
        if claim_id:
            return claim_id
    return None


def _event_claim_id(event: Event) -> str | None:
    claim_id = event.get("claim_id") or event.get("resident_claim_id")
    return str(claim_id) if claim_id else None


def _first_event(
    events: list[Event],
    event_name: str,
    *,
    predicate: Any | None = None,
) -> Event | None:
    for event in events:
        if event.get("event") != event_name:
            continue
        if predicate is not None and not predicate(event):
            continue
        return event
    return None


def _first_event_after(
    events: list[Event],
    event_name: str,
    after: Event | None,
    *,
    predicate: Any | None = None,
) -> Event | None:
    if after is None:
        return None
    for event in events:
        if _event_order(event) <= _event_order(after):
            continue
        if event.get("event") != event_name:
            continue
        if predicate is not None and not predicate(event):
            continue
        return event
    return None


def _first_transfer(
    events: list[Event],
    transfer_type: tuple[str, str],
    *,
    success: bool,
    after: Event | None,
) -> Event | None:
    if after is None:
        return None
    for event in events:
        if _event_order(event) <= _event_order(after):
            continue
        if event.get("event") != "offload_worker_transfer_finished":
            continue
        if tuple(event.get("transfer_type") or ()) != transfer_type:
            continue
        if bool(event.get("success")) != success:
            continue
        return event
    return None


def _ordered(*events: Event | None) -> bool:
    present = [event for event in events if event is not None]
    return len(present) == len(events) and all(
        _event_order(left) < _event_order(right)
        for left, right in zip(present, present[1:])
    )


def _event_order(event: Event) -> int:
    return int(event.get("event_sequence", event.get("timestamp_ns", 0)))


def _compact(event: Event | None) -> dict[str, Any] | None:
    if event is None:
        return None
    keys = (
        "event",
        "event_sequence",
        "request_id",
        "claim_id",
        "resident_claim_id",
        "job_id",
        "transfer_type",
        "success",
        "key_count",
        "num_hit_tokens",
        "failure_reason",
        "outcome_claim_id",
        "blocking_claim_ids",
        "scheduler_finish_status",
    )
    return {key: event[key] for key in keys if key in event}
