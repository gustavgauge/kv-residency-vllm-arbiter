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


@dataclass(frozen=True)
class MultiClaimAttributionEvaluation:
    gate_summary: dict[str, Any]
    event_counts: dict[str, int]
    analyzer_runtime_ns: int

    @property
    def attribution_success(self) -> bool:
        return not self.gate_summary["missing_requirements"]

    def to_record(self) -> dict[str, Any]:
        return {
            "gate_summary": self.gate_summary,
            "event_counts": self.event_counts,
            "analyzer_runtime_ns": self.analyzer_runtime_ns,
            "attribution_success": self.attribution_success,
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
    identity_ambiguities = _claim_identity_ambiguities(claim_events)

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
    scheduler_restoration_failed = _first_event_after(
        claim_events,
        "scheduler_resident_claim_restoration_failed",
        failed_transfer,
        predicate=lambda event: event.get("outcome_claim_id") == claim_id
        and bool(event.get("scheduler_side_failure_outcome")),
    )
    scheduler_refusal = _first_event_after(
        claim_events,
        "scheduler_active_request_refused",
        scheduler_restoration_failed,
        predicate=lambda event: event.get("outcome_claim_id") == claim_id
        and claim_id in event.get("blocking_claim_ids", [])
        and bool(event.get("scheduler_side_refusal"))
        and not bool(event.get("native_scheduler_admission_refusal")),
    )
    scheduler_last_event = scheduler_refusal or scheduler_restoration_failed
    request_termination = _first_request_termination_after(
        claim_events,
        scheduler_last_event,
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
        scheduler_restoration_failed or restoration_failed,
    )
    fallback_recompute_observed_after_failure = (
        fallback_satisfied_after_failure is not None
    )
    connector_level_outcome_present = restoration_failed is not None and refusal is not None
    scheduler_side_failure_outcome_present = scheduler_restoration_failed is not None
    scheduler_side_refusal_present = scheduler_refusal is not None
    scheduler_side_claim_match = (
        scheduler_restoration_failed is not None
        and scheduler_restoration_failed.get("outcome_claim_id") == claim_id
        and scheduler_refusal is not None
        and scheduler_refusal.get("outcome_claim_id") == claim_id
        and claim_id in scheduler_refusal.get("blocking_claim_ids", [])
    )
    scheduler_event_before_or_at_termination = _event_before_or_at(
        scheduler_refusal,
        request_termination,
    )
    native_scheduler_admission_refusal = any(
        bool(event.get("native_scheduler_admission_refusal"))
        for event in (scheduler_restoration_failed, scheduler_refusal)
        if event is not None
    )

    observation_missing = []
    if request_initialized is None:
        observation_missing.append("claim_metadata_before_lifecycle")
    if identity_ambiguities:
        observation_missing.append("ambiguous_claim_cache_identity")
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
    if identity_ambiguities:
        failure_missing.append("ambiguous_claim_cache_identity")
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
    if not scheduler_side_failure_outcome_present:
        failure_missing.append("scheduler_side_restoration_failed")
    if not scheduler_side_refusal_present:
        failure_missing.append("scheduler_side_active_request_refused")
    if not scheduler_side_claim_match:
        failure_missing.append("scheduler_side_claim_match")
    if not scheduler_event_before_or_at_termination:
        failure_missing.append("scheduler_event_before_or_at_termination")
    if native_scheduler_admission_refusal:
        failure_missing.append("native_scheduler_admission_refusal_misclassified")
    if fallback_recompute_observed_after_failure:
        failure_missing.append("no_fallback_recompute_counted_as_satisfaction")

    ordered_failure = _ordered(
        request_initialized,
        store_created,
        store_transfer,
        lookup_hit,
        restore_required,
        load_created,
        failed_transfer,
        scheduler_restoration_failed,
        scheduler_refusal,
        request_termination,
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
            "fallback_recompute_observed_after_failure": (
                fallback_recompute_observed_after_failure
            ),
            "fallback_recompute_counted_as_satisfaction": False,
            "ordinary_offload_without_claim_rejected": (
                claim_id is None and _has_connector_activity(event_list)
            ),
        },
        "connector_level_outcome_present": connector_level_outcome_present,
        "scheduler_side_failure_outcome_present": (
            scheduler_side_failure_outcome_present
        ),
        "scheduler_side_refusal_present": scheduler_side_refusal_present,
        "scheduler_side_claim_match": scheduler_side_claim_match,
        "scheduler_event_before_or_at_termination": (
            scheduler_event_before_or_at_termination
        ),
        "native_scheduler_admission_refusal": native_scheduler_admission_refusal,
        "finish_status": _first_nonempty_field(
            scheduler_refusal,
            scheduler_restoration_failed,
            refusal,
            key="finish_status",
        ),
        "finish_reason": _first_nonempty_field(
            scheduler_refusal,
            scheduler_restoration_failed,
            refusal,
            key="finish_reason",
        ),
        "blocking_claim_ids": _first_nonempty_field(
            scheduler_refusal,
            refusal,
            key="blocking_claim_ids",
        )
        or [],
        "claim_identity_ambiguities": identity_ambiguities,
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
            "scheduler_restoration_failed": _compact(scheduler_restoration_failed),
            "scheduler_refusal": _compact(scheduler_refusal),
            "request_termination": _compact(request_termination),
            "load_failed": _compact(load_failed),
            "restoration_failed": _compact(restoration_failed),
            "refusal": _compact(refusal),
        },
        "claim_boundary": (
            "Patched pydev vLLM OffloadingConnector plus scheduler-side "
            "invalid-KV-load boundary evidence only; this is not native upstream "
            "ResidentClaim support, production offload performance, or "
            "pre-admission refusal."
        ),
    }
    analyzer_runtime_ns = time.perf_counter_ns() - start
    return PydevConnectorEvaluation(
        gate_summary=summary,
        event_counts=counts,
        analyzer_runtime_ns=analyzer_runtime_ns,
    )


def evaluate_multi_claim_attribution_events(
    events: Iterable[Event],
    *,
    target_claim_id: str,
    non_target_claim_ids: Iterable[str],
) -> MultiClaimAttributionEvaluation:
    """Check that scheduler-boundary failure/refusal attribution names one claim.

    This is an attribution control for traces that contain at least two accepted
    ResidentClaim-shaped identities. It intentionally does not widen the
    offloadability claim: a pass only means the trace does not smear the target
    restoration failure onto nearby non-target claims.
    """

    start = time.perf_counter_ns()
    event_list = sorted((dict(event) for event in events), key=_event_order)
    counts = event_counts(event_list)
    non_targets = sorted({str(claim_id) for claim_id in non_target_claim_ids})
    target = str(target_claim_id)

    target_eval = evaluate_pydev_connector_events(
        event_list,
        expected_claim_id=target,
    )
    non_target_evaluations = {
        claim_id: evaluate_pydev_connector_events(
            event_list,
            expected_claim_id=claim_id,
        ).to_record()
        for claim_id in non_targets
    }

    scheduler_failure_events = [
        event
        for event in event_list
        if event.get("event")
        in {
            "scheduler_resident_claim_restoration_failed",
            "scheduler_active_request_refused",
        }
    ]
    target_scheduler_failures = [
        event
        for event in scheduler_failure_events
        if _event_claim_id(event) == target
        and event.get("outcome_claim_id") == target
    ]
    target_scheduler_restoration_failed = [
        event
        for event in target_scheduler_failures
        if event.get("event") == "scheduler_resident_claim_restoration_failed"
    ]
    target_scheduler_refusals = [
        event
        for event in target_scheduler_failures
        if event.get("event") == "scheduler_active_request_refused"
    ]
    scheduler_events_only_target = bool(scheduler_failure_events) and all(
        _event_claim_id(event) == target
        and event.get("outcome_claim_id") == target
        for event in scheduler_failure_events
    )
    blocking_claim_ids_only_target = bool(scheduler_failure_events) and all(
        _blocking_claim_ids(event) == [target] for event in scheduler_failure_events
    )

    non_target_failure_events = [
        event
        for event in event_list
        if _event_claim_id(event) in set(non_targets)
        and event.get("event")
        in {
            "scheduler_resident_claim_restoration_failed",
            "scheduler_active_request_refused",
            "resident_claim_restoration_failed",
            "active_request_refused",
        }
    ]
    non_target_claim_status = {
        claim_id: {
            "observation_success": bool(
                non_target_evaluations[claim_id]["connector_observation_success"]
            ),
            "failure_outcome_success": bool(
                non_target_evaluations[claim_id][
                    "restoration_failure_outcome_success"
                ]
            ),
            "failure_or_refusal_events": [
                _compact(event)
                for event in non_target_failure_events
                if _event_claim_id(event) == claim_id
            ],
        }
        for claim_id in non_targets
    }
    non_targets_restored_or_not_failed = all(
        status["observation_success"] or not status["failure_or_refusal_events"]
        for status in non_target_claim_status.values()
    )
    non_target_failure_or_refusal_attribution = any(
        status["failure_or_refusal_events"]
        for status in non_target_claim_status.values()
    )

    missing = []
    if not target_eval.restoration_failure_outcome_success:
        missing.append("target_claim_failure_outcome_gate")
    if not target_scheduler_restoration_failed:
        missing.append("scheduler_resident_claim_restoration_failed_target")
    if not target_scheduler_refusals:
        missing.append("scheduler_active_request_refused_target")
    if not scheduler_events_only_target:
        missing.append("scheduler_failure_events_name_only_target")
    if not blocking_claim_ids_only_target:
        missing.append("blocking_claim_ids_name_only_target")
    if non_target_failure_or_refusal_attribution:
        missing.append("non_target_failure_or_refusal_attribution")
    if not non_targets_restored_or_not_failed:
        missing.append("non_target_restore_success_or_not_failed")

    summary = {
        "schema_version": 1,
        "gate": "multi_claim_scheduler_boundary_attribution",
        "target_claim_id": target,
        "non_target_claim_ids": non_targets,
        "missing_requirements": sorted(set(missing)),
        "target_failure_outcome_gate": target_eval.restoration_failure_outcome_success,
        "target_scheduler_restoration_failed_count": len(
            target_scheduler_restoration_failed
        ),
        "target_scheduler_refusal_count": len(target_scheduler_refusals),
        "scheduler_events_only_target": scheduler_events_only_target,
        "blocking_claim_ids_only_target": blocking_claim_ids_only_target,
        "non_targets_restored_or_not_failed": non_targets_restored_or_not_failed,
        "non_target_failure_or_refusal_attribution": (
            non_target_failure_or_refusal_attribution
        ),
        "target_gate_summary": target_eval.gate_summary,
        "non_target_claim_status": non_target_claim_status,
        "scheduler_failure_events": [
            _compact(event) for event in scheduler_failure_events
        ],
        "claim_boundary": (
            "Attribution control over local patched pydev vLLM "
            "OffloadingConnector plus scheduler-side invalid-KV-load boundary "
            "events only; not upstream ResidentClaim support, production "
            "offload performance, or pre-admission refusal."
        ),
    }
    analyzer_runtime_ns = time.perf_counter_ns() - start
    return MultiClaimAttributionEvaluation(
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


def _claim_identity_ambiguities(events: list[Event]) -> dict[str, list[str]]:
    stable_identity_fields = (
        "predicate_id",
        "prefix_id",
        "reusable_object_id",
        "cache_identity",
        "request_token_map_id",
    )
    ambiguous: dict[str, list[str]] = {}
    for field in stable_identity_fields:
        values = sorted(
            {
                json.dumps(event[field], sort_keys=True)
                if isinstance(event[field], (dict, list))
                else str(event[field])
                for event in events
                if event.get(field) not in (None, "")
            }
        )
        if len(values) > 1:
            ambiguous[field] = values
    return ambiguous


def _event_claim_id(event: Event) -> str | None:
    claim_id = event.get("claim_id") or event.get("resident_claim_id")
    return str(claim_id) if claim_id else None


def _blocking_claim_ids(event: Event) -> list[str]:
    value = event.get("blocking_claim_ids")
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value)


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


def _first_request_termination_after(
    events: list[Event],
    after: Event | None,
) -> Event | None:
    pending = _first_event_after(
        events,
        "offload_request_finished_pending_jobs",
        after,
    )
    no_pending = _first_event_after(
        events,
        "offload_request_finished_no_pending_jobs",
        after,
    )
    candidates = [event for event in (pending, no_pending) if event is not None]
    if not candidates:
        return None
    return min(candidates, key=_event_order)


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


def _event_before_or_at(left: Event | None, right: Event | None) -> bool:
    if left is None or right is None:
        return False
    return _event_order(left) <= _event_order(right)


def _event_order(event: Event) -> int:
    return int(event.get("event_sequence", event.get("timestamp_ns", 0)))


def _first_nonempty_field(*events: Event | None, key: str) -> Any | None:
    for event in events:
        if event is None:
            continue
        value = event.get(key)
        if value is not None:
            return value
    return None


def _has_connector_activity(events: list[Event]) -> bool:
    return any(
        str(event.get("event", "")).startswith("offload_")
        or str(event.get("event", "")).startswith("resident_claim_")
        for event in events
    )


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
        "finish_status",
        "finish_reason",
        "invalid_block_ids",
        "invalid_block_count",
        "scheduler_failure_policy",
        "scheduler_side_failure_outcome",
        "scheduler_side_refusal",
        "native_scheduler_refusal",
        "native_scheduler_admission_refusal",
    )
    return {key: event[key] for key in keys if key in event}
