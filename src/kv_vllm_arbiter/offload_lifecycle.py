"""Reference lifecycle/outcome hook for ResidentClaim offloadability.

This module is intentionally a reference state machine. It does not claim real
vLLM host-offload performance. Its purpose is to make the offloadable contract
executable: accepted claim, materialization, offload, restore-before-reuse, and
fail-closed restoration-unavailable outcomes.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


Event = dict[str, Any]
ALLOWED_FAILURE_OUTCOMES = {"refusal", "demotion", "expiry", "harm"}
PRIMARY_TIER = "gpu_kv_cache"
OFFLOAD_TIER = "host_offload_tier"


@dataclass(frozen=True)
class OffloadLifecycleConfig:
    run_id: str = "reference-offload-lifecycle"
    policy: str = "reference_offload_hook"
    claim_id: str = "claim:reference-offload"
    request_id: str = "resident"
    reuse_request_id: str = "reuse"
    failure_request_id: str = "reuse-failure"
    prefix_id: str = "prefix:reference"
    reusable_object_id: str = "kv-object:reference-prefix"
    predicate_id: str = "predicate:leading-prefix-8"
    materialization_predicate: str = "leading_prefix_at_least(8)"
    request_token_map_id: str = "token-map:reference-prefix-v1"
    cache_identity: str = "patched-vllm-reference-cache:v1"
    block_count: int = 8
    usable_blocks: int = 16
    block_size_tokens: int = 16
    primary_tier: str = PRIMARY_TIER
    offload_tier: str = OFFLOAD_TIER


@dataclass(frozen=True)
class OffloadLifecycleEvaluation:
    gate_summary: dict[str, Any]
    event_counts: dict[str, int]
    success_generation: int | None
    failure_generation: int | None
    active_claim_count: int
    claim_registry_size: int

    @property
    def passes_reference_gate(self) -> bool:
        missing = self.gate_summary.get("reference_missing_requirements", [])
        return not missing

    def to_record(self) -> dict[str, Any]:
        return {
            "gate_summary": self.gate_summary,
            "event_counts": self.event_counts,
            "success_generation": self.success_generation,
            "failure_generation": self.failure_generation,
            "active_claim_count": self.active_claim_count,
            "claim_registry_size": self.claim_registry_size,
            "passes_reference_gate": self.passes_reference_gate,
        }


class ReferenceOffloadLifecycleHook:
    """Small claim-scoped offload lifecycle hook with deterministic ordering."""

    def __init__(
        self,
        config: OffloadLifecycleConfig | None = None,
        *,
        emit_events: bool = True,
    ) -> None:
        self.config = config or OffloadLifecycleConfig()
        self.emit_events = emit_events
        self.events: list[Event] = []
        self.event_sequence = 0
        self.lifecycle_generation = 0
        self.offload_generation = 0
        self.cache_tier = self.config.primary_tier
        self.claim_registry: dict[str, dict[str, Any]] = {}
        self.block_ids = [1000 + index for index in range(self.config.block_count)]

    def accept_claim(self) -> Event:
        self.lifecycle_generation += 1
        self.claim_registry[self.config.claim_id] = {
            "claim_id": self.config.claim_id,
            "status": "accepted",
            "block_count": self.config.block_count,
        }
        return self._emit(
            "resident_claim_accepted",
            request_id=self.config.request_id,
            claim_registration="pre_registered",
            resident_blocks_required=self.config.block_count,
            resident_blocks_materialized=0,
            protection_mode="offloadable_reference",
            predicted_value=1.0,
            confidence=1.0,
        )

    def materialize_claim(self) -> Event:
        self._require_claim()
        self.claim_registry[self.config.claim_id]["status"] = "materialized"
        self.claim_registry[self.config.claim_id]["block_ids"] = list(self.block_ids)
        return self._emit(
            "resident_claim_materialized",
            request_id=self.config.request_id,
            resident_blocks_required=self.config.block_count,
            resident_blocks_materialized=self.config.block_count,
            useful_threshold_blocks=self.config.block_count,
            leading_blocks_survived=self.config.block_count,
            predicate="leading_prefix_at_least",
            predicate_materialized=True,
            block_ids=list(self.block_ids),
            block_count_footprint=self.config.block_count,
            cache_tier=self.cache_tier,
        )

    def offload_claim(self, *, reason: str = "capacity_pressure") -> Event:
        self._require_claim()
        self.offload_generation += 1
        self.cache_tier = self.config.offload_tier
        self.claim_registry[self.config.claim_id]["status"] = "restoration_required"
        self.claim_registry[self.config.claim_id][
            "offload_generation"
        ] = self.offload_generation
        return self._emit(
            "resident_claim_offloaded",
            request_id=self.config.request_id,
            arbiter_action=reason,
            cache_tier=self.config.offload_tier,
            cache_tier_from=self.config.primary_tier,
            cache_tier_to=self.config.offload_tier,
            source_tier=self.config.primary_tier,
            destination_tier=self.config.offload_tier,
            restoration_required=True,
            block_ids=list(self.block_ids),
            block_count_footprint=self.config.block_count,
        )

    def require_restore(self, *, request_id: str | None = None) -> Event:
        self._require_claim()
        return self._emit(
            "resident_claim_restore_required",
            request_id=request_id or self.config.reuse_request_id,
            cache_tier=self.cache_tier,
            restoration_required=True,
            reuse_requires_restoration=True,
            predicate_satisfied_from_primary=False,
            block_count_footprint=self.config.block_count,
        )

    def restore_claim(
        self,
        *,
        request_id: str | None = None,
        source: str = "offload_tier",
    ) -> Event:
        self._require_claim()
        restored_from_offload = source == "offload_tier"
        source_tier = self.config.offload_tier if restored_from_offload else source
        self.cache_tier = self.config.primary_tier
        self.claim_registry[self.config.claim_id]["status"] = "restored"
        return self._emit(
            "resident_claim_restored",
            request_id=request_id or self.config.reuse_request_id,
            cache_tier=self.config.primary_tier,
            cache_tier_from=source_tier,
            cache_tier_to=self.config.primary_tier,
            source_tier=source_tier,
            destination_tier=self.config.primary_tier,
            restoration_source=source,
            restored_from_offload_tier=restored_from_offload,
            restoration_completed=True,
            block_ids=list(self.block_ids),
            block_count_footprint=self.config.block_count,
        )

    def reuse_after_restore(self, *, request_id: str | None = None) -> Event:
        self._require_claim()
        return self._emit(
            "resident_claim_reuse_after_restore",
            request_id=request_id or self.config.reuse_request_id,
            cache_tier=self.config.primary_tier,
            reuse_requires_restoration=True,
            predicate_satisfied=True,
            predicate_satisfied_from_primary=True,
            block_count_footprint=self.config.block_count,
        )

    def fail_restore(
        self,
        *,
        request_id: str | None = None,
        outcome_type: str = "refusal",
    ) -> Event:
        self._require_claim()
        if outcome_type not in ALLOWED_FAILURE_OUTCOMES:
            raise ValueError(f"unsupported outcome_type: {outcome_type}")

        failure_request_id = request_id or self.config.failure_request_id
        failure = self._emit(
            "resident_claim_restoration_failed",
            request_id=failure_request_id,
            cache_tier=self.cache_tier,
            restoration_required=True,
            controlled_restoration_unavailable=True,
            injected_restoration_failure=True,
            restoration_failure_reason="controlled_unavailable",
            claim_scoped_outcome=True,
            claim_scoped_outcome_type=outcome_type,
            outcome_type=outcome_type,
            outcome_claim_id=self.config.claim_id,
            block_count_footprint=self.config.block_count,
        )

        if outcome_type == "refusal":
            self._emit(
                "active_request_refused",
                request_id=failure_request_id,
                claim_id=self.config.claim_id,
                arbiter_action="restore_unavailable_refuse",
                blocking_claim_ids=[self.config.claim_id],
                outcome_type="refusal",
                outcome_claim_id=self.config.claim_id,
                restoration_failure_event_sequence=failure["event_sequence"],
                feasibility="infeasible_restore_claimed_kv",
            )
        elif outcome_type == "demotion":
            self._emit_outcome("resident_claim_demoted", outcome_type, failure)
        elif outcome_type == "expiry":
            self._emit_outcome("resident_claim_expired", outcome_type, failure)
        elif outcome_type == "harm":
            self._emit_outcome("resident_claim_harmed", outcome_type, failure)
        return failure

    def _emit_outcome(
        self,
        event_name: str,
        outcome_type: str,
        failure: Event,
    ) -> Event:
        return self._emit(
            event_name,
            request_id=self.config.failure_request_id,
            cache_tier=self.cache_tier,
            arbiter_action=f"restore_unavailable_{outcome_type}",
            outcome_type=outcome_type,
            outcome_claim_id=self.config.claim_id,
            restoration_failure_event_sequence=failure["event_sequence"],
            block_count_footprint=self.config.block_count,
        )

    def _require_claim(self) -> None:
        if self.config.claim_id not in self.claim_registry:
            raise RuntimeError("claim must be accepted before lifecycle transitions")

    def _emit(self, event: str, request_id: str, **fields: Any) -> Event:
        self.event_sequence += 1
        record: Event = {
            "schema_version": 1,
            "timestamp_ns": time.time_ns(),
            "event_sequence": self.event_sequence,
            "run_id": self.config.run_id,
            "event": event,
            "request_id": request_id,
            "claim_id": fields.pop("claim_id", self.config.claim_id),
            "prefix_id": self.config.prefix_id,
            "policy": self.config.policy,
            "usable_blocks": self.config.usable_blocks,
            "lifecycle_generation": self.lifecycle_generation,
            "offload_generation": self.offload_generation,
            "predicate_id": self.config.predicate_id,
            "materialization_predicate": self.config.materialization_predicate,
            "reusable_object_id": self.config.reusable_object_id,
            "request_token_map_id": self.config.request_token_map_id,
            "cache_identity": self.config.cache_identity,
        }
        record.update(fields)
        if self.emit_events:
            self.events.append(record)
        return record


def build_reference_trace(
    scenario: str,
    *,
    config: OffloadLifecycleConfig | None = None,
    emit_events: bool = True,
    failure_outcome: str = "refusal",
) -> list[Event]:
    """Build one executable reference trace for a named offload scenario."""

    hook = ReferenceOffloadLifecycleHook(config, emit_events=emit_events)
    if scenario == "baseline_no_hook":
        return []
    if scenario == "generic_substrate":
        return build_generic_substrate_trace(config or OffloadLifecycleConfig())

    hook.accept_claim()
    hook.materialize_claim()

    if scenario == "positive_bundle":
        hook.offload_claim(reason="capacity_pressure_success_generation")
        hook.require_restore(request_id=hook.config.reuse_request_id)
        hook.restore_claim(request_id=hook.config.reuse_request_id)
        hook.reuse_after_restore(request_id=hook.config.reuse_request_id)
        hook.offload_claim(reason="capacity_pressure_failure_generation")
        hook.require_restore(request_id=hook.config.failure_request_id)
        hook.fail_restore(
            request_id=hook.config.failure_request_id,
            outcome_type=failure_outcome,
        )
    elif scenario == "success_restore":
        hook.offload_claim()
        hook.require_restore(request_id=hook.config.reuse_request_id)
        hook.restore_claim(request_id=hook.config.reuse_request_id)
        hook.reuse_after_restore(request_id=hook.config.reuse_request_id)
    elif scenario == "failure_refusal":
        hook.offload_claim()
        hook.require_restore(request_id=hook.config.failure_request_id)
        hook.fail_restore(
            request_id=hook.config.failure_request_id,
            outcome_type=failure_outcome,
        )
    elif scenario == "claim_offload_no_restore":
        hook.offload_claim()
    elif scenario == "restore_after_reuse":
        hook.offload_claim()
        hook.require_restore(request_id=hook.config.reuse_request_id)
        hook.reuse_after_restore(request_id=hook.config.reuse_request_id)
        hook.restore_claim(request_id=hook.config.reuse_request_id)
    elif scenario == "wrong_claim_failure_outcome":
        hook.offload_claim()
        hook.require_restore(request_id=hook.config.failure_request_id)
        failure = hook.fail_restore(
            request_id=hook.config.failure_request_id,
            outcome_type=failure_outcome,
        )
        failure["outcome_claim_id"] = "claim:wrong"
        for event in hook.events:
            if event.get("restoration_failure_event_sequence") == failure["event_sequence"]:
                event["outcome_claim_id"] = "claim:wrong"
                event["blocking_claim_ids"] = ["claim:wrong"]
    elif scenario == "fallback_recompute":
        hook.offload_claim()
        hook.require_restore(request_id=hook.config.reuse_request_id)
        hook.restore_claim(
            request_id=hook.config.reuse_request_id,
            source="fallback_recompute",
        )
        hook.reuse_after_restore(request_id=hook.config.reuse_request_id)
    elif scenario == "post_hoc_claim_naming":
        for event in hook.events:
            if event["event"] == "resident_claim_accepted":
                event["claim_registration"] = "post_hoc"
        hook.offload_claim()
        hook.require_restore(request_id=hook.config.reuse_request_id)
        hook.restore_claim(request_id=hook.config.reuse_request_id)
        hook.reuse_after_restore(request_id=hook.config.reuse_request_id)
    elif scenario == "missing_identity":
        hook.offload_claim()
        hook.require_restore(request_id=hook.config.reuse_request_id)
        hook.restore_claim(request_id=hook.config.reuse_request_id)
        hook.reuse_after_restore(request_id=hook.config.reuse_request_id)
        for event in hook.events:
            event.pop("request_token_map_id", None)
    else:
        raise ValueError(f"unknown scenario: {scenario}")
    return hook.events


def build_generic_substrate_trace(config: OffloadLifecycleConfig) -> list[Event]:
    now = time.time_ns()
    return [
        {
            "schema_version": 1,
            "timestamp_ns": now,
            "event_sequence": 1,
            "run_id": config.run_id,
            "event": "generic_kv_blocks_offloaded",
            "request_id": "unknown",
            "claim_id": None,
            "prefix_id": None,
            "policy": config.policy,
            "usable_blocks": config.usable_blocks,
            "generic_offload_blocks": config.block_count,
            "cache_tier_to": config.offload_tier,
        },
        {
            "schema_version": 1,
            "timestamp_ns": now + 1,
            "event_sequence": 2,
            "run_id": config.run_id,
            "event": "generic_kv_blocks_onboarded",
            "request_id": "unknown",
            "claim_id": None,
            "prefix_id": None,
            "policy": config.policy,
            "usable_blocks": config.usable_blocks,
            "generic_onboard_blocks": config.block_count,
            "cache_tier_to": config.primary_tier,
        },
    ]


def evaluate_offload_lifecycle_events(
    events: Iterable[Event],
    *,
    evidence_path: str | None = None,
) -> OffloadLifecycleEvaluation:
    event_list = sorted((dict(event) for event in events), key=_event_order)
    counts = event_counts(event_list)
    claim_id = _first_claim_id(event_list)
    claim_events = [
        event for event in event_list if claim_id and event.get("claim_id") == claim_id
    ]

    accepted = _first_event(claim_events, "resident_claim_accepted")
    materialized = _first_event(claim_events, "resident_claim_materialized")
    success = _find_success_path(claim_events)
    failure = _find_failure_path(claim_events)

    predicate_id = _first_field(claim_events, "predicate_id")
    materialization_predicate = _first_field(
        claim_events,
        "materialization_predicate",
    )
    reusable_object_id = _first_field(claim_events, "reusable_object_id")
    request_token_map_id = _first_field(claim_events, "request_token_map_id")
    cache_identity = _first_field(claim_events, "cache_identity")
    prefix_id = _first_field(claim_events, "prefix_id")

    missing = []
    if accepted is None or accepted.get("claim_registration") != "pre_registered":
        missing.append("pre_registered_accepted_claim")
    if not claim_id or not predicate_id or not materialization_predicate:
        missing.append("stable_claim_id_and_fixed_materialization_predicate")
    if not reusable_object_id:
        missing.append("reusable_object_id")
    if not cache_identity or not request_token_map_id:
        missing.append("fixed_cache_identity_and_deterministic_request_token_map")
    if materialized is None or not materialized.get("predicate_materialized"):
        missing.append("materialization_predicate")
    if success is None:
        missing.append("offload_restorability")
    if failure is None:
        missing.append("restoration_failure_outcome")
    ordered = _ordered_reference_lifecycle(accepted, materialized, success, failure)
    if not ordered:
        missing.append("ordered_lifecycle_events")

    gate_summary: dict[str, Any] = {
        "schema_version": 1,
        "claim": {
            "claim_id": claim_id,
            "pre_registered_accepted_claim": accepted is not None
            and accepted.get("claim_registration") == "pre_registered",
            "stable_claim_id": bool(claim_id)
            and all(
                event.get("claim_id") == claim_id
                for event in claim_events
                if event.get("claim_id") is not None
            ),
            "post_hoc_claim_naming": bool(
                accepted and accepted.get("claim_registration") == "post_hoc"
            ),
            "predicate_id": predicate_id,
            "materialization_predicate": materialization_predicate,
            "materialization_predicate_fixed": bool(materialization_predicate),
            "reusable_object_id": reusable_object_id,
            "cache_runtime_identity_fixed": bool(cache_identity),
            "deterministic_request_token_map": bool(request_token_map_id),
            "request_token_map_id": request_token_map_id,
            "prefix_id": prefix_id,
        },
        "offload": {
            "kv_state_moved_to_offload_tier": bool(success),
            "claim_joined_offload": bool(success),
            "offload_generation": success["generation"] if success else None,
        },
        "restoration": {
            "later_reuse_required_restoration": bool(success),
            "completed_before_reuse_satisfied_predicate": bool(success),
            "restored_from_offload_tier": bool(success),
            "restoration_source": (
                success["restored"].get("restoration_source") if success else None
            ),
            "reuse_event_sequence": (
                success["reuse"]["event_sequence"] if success else None
            ),
        },
        "failure_injection": {
            "injected_restoration_failure": bool(failure),
            "controlled_restoration_unavailable": bool(failure),
            "claim_scoped_outcome": bool(failure),
            "claim_scoped_outcome_type": (
                failure["failure"].get("claim_scoped_outcome_type")
                if failure
                else None
            ),
            "outcome_claim_id": (
                failure["failure"].get("outcome_claim_id") if failure else None
            ),
            "outcome_event": failure["outcome"] if failure else None,
        },
        "lifecycle": {
            "ordered_lifecycle_events": ordered,
            "success_generation": success["generation"] if success else None,
            "failure_generation": failure["generation"] if failure else None,
        },
        "reference_missing_requirements": sorted(set(missing)),
    }
    if evidence_path:
        gate_summary["evidence_anchors"] = {
            "offload_restorability": [
                {
                    "kind": "trace",
                    "path": evidence_path,
                    "note": "Reference hook trace contains offload, restore-before-reuse, and reuse events.",
                }
            ],
            "restoration_failure_outcome": [
                {
                    "kind": "trace",
                    "path": evidence_path,
                    "note": "Reference hook trace contains controlled restoration failure and claim-scoped outcome.",
                }
            ],
        }

    return OffloadLifecycleEvaluation(
        gate_summary=gate_summary,
        event_counts=counts,
        success_generation=success["generation"] if success else None,
        failure_generation=failure["generation"] if failure else None,
        active_claim_count=len({claim_id} if claim_id else set()),
        claim_registry_size=len({claim_id} if claim_id else set()),
    )


def write_jsonl(path: Path, events: Iterable[Event]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(event, sort_keys=True, separators=(",", ":"))
        for event in events
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_jsonl(path: Path) -> list[Event]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def event_counts(events: Iterable[Event]) -> dict[str, int]:
    event_list = list(events)
    return {
        event_name: sum(1 for event in event_list if event.get("event") == event_name)
        for event_name in sorted({str(event.get("event")) for event in event_list})
    }


def _find_success_path(events: list[Event]) -> dict[str, Any] | None:
    for offloaded in _events_named(events, "resident_claim_offloaded"):
        generation = int(offloaded.get("offload_generation", 0))
        if not (
            offloaded.get("cache_tier_from") == PRIMARY_TIER
            and offloaded.get("cache_tier_to") == OFFLOAD_TIER
        ):
            continue
        required = _first_after(
            events,
            "resident_claim_restore_required",
            offloaded,
            generation,
        )
        restored = _first_after(events, "resident_claim_restored", required, generation)
        reuse = _first_after(
            events,
            "resident_claim_reuse_after_restore",
            restored,
            generation,
        )
        if required is None or restored is None or reuse is None:
            continue
        if not required.get("reuse_requires_restoration"):
            continue
        if not _restored_from_offload(restored):
            continue
        if not reuse.get("predicate_satisfied"):
            continue
        return {
            "generation": generation,
            "offloaded": offloaded,
            "required": required,
            "restored": restored,
            "reuse": reuse,
        }
    return None


def _find_failure_path(events: list[Event]) -> dict[str, Any] | None:
    for offloaded in _events_named(events, "resident_claim_offloaded"):
        generation = int(offloaded.get("offload_generation", 0))
        required = _first_after(
            events,
            "resident_claim_restore_required",
            offloaded,
            generation,
        )
        failure = _first_after(
            events,
            "resident_claim_restoration_failed",
            required,
            generation,
        )
        if required is None or failure is None:
            continue
        outcome_type = str(failure.get("claim_scoped_outcome_type", ""))
        if outcome_type not in ALLOWED_FAILURE_OUTCOMES:
            continue
        if failure.get("outcome_claim_id") != failure.get("claim_id"):
            continue
        if not (
            failure.get("controlled_restoration_unavailable")
            or failure.get("injected_restoration_failure")
        ):
            continue
        outcome = _find_outcome_after(events, failure, outcome_type)
        if outcome is None:
            continue
        return {
            "generation": generation,
            "offloaded": offloaded,
            "required": required,
            "failure": failure,
            "outcome": outcome,
        }
    return None


def _find_outcome_after(
    events: list[Event],
    failure: Event,
    outcome_type: str,
) -> Event | None:
    expected_claim_id = failure.get("claim_id")
    for event in events:
        if _event_order(event) <= _event_order(failure):
            continue
        if outcome_type == "refusal" and event.get("event") != "active_request_refused":
            continue
        if outcome_type == "demotion" and event.get("event") != "resident_claim_demoted":
            continue
        if outcome_type == "expiry" and event.get("event") != "resident_claim_expired":
            continue
        if outcome_type == "harm" and event.get("event") != "resident_claim_harmed":
            continue
        if event.get("outcome_claim_id") != expected_claim_id:
            continue
        if outcome_type == "refusal" and expected_claim_id not in event.get(
            "blocking_claim_ids",
            [],
        ):
            continue
        return event
    return None


def _ordered_reference_lifecycle(
    accepted: Event | None,
    materialized: Event | None,
    success: dict[str, Any] | None,
    failure: dict[str, Any] | None,
) -> bool:
    if accepted is None or materialized is None or success is None or failure is None:
        return False
    return (
        _event_order(accepted)
        < _event_order(materialized)
        < _event_order(success["offloaded"])
        < _event_order(success["required"])
        < _event_order(success["restored"])
        < _event_order(success["reuse"])
        < _event_order(failure["offloaded"])
        < _event_order(failure["required"])
        < _event_order(failure["failure"])
        < _event_order(failure["outcome"])
    )


def _restored_from_offload(event: Event) -> bool:
    return (
        bool(event.get("restored_from_offload_tier"))
        and event.get("restoration_source") == "offload_tier"
        and event.get("cache_tier_from") == OFFLOAD_TIER
        and event.get("cache_tier_to") == PRIMARY_TIER
    )


def _first_after(
    events: list[Event],
    event_name: str,
    previous: Event | None,
    generation: int,
) -> Event | None:
    if previous is None:
        return None
    for event in events:
        if event.get("event") != event_name:
            continue
        if int(event.get("offload_generation", 0)) != generation:
            continue
        if _event_order(event) > _event_order(previous):
            return event
    return None


def _events_named(events: list[Event], event_name: str) -> list[Event]:
    return [event for event in events if event.get("event") == event_name]


def _first_event(events: list[Event], event_name: str) -> Event | None:
    for event in events:
        if event.get("event") == event_name:
            return event
    return None


def _first_claim_id(events: list[Event]) -> str | None:
    for event in events:
        claim_id = event.get("claim_id")
        if claim_id:
            return str(claim_id)
    return None


def _first_field(events: list[Event], field: str) -> Any:
    for event in events:
        value = event.get(field)
        if value not in (None, ""):
            return value
    return None


def _event_order(event: Event) -> int:
    return int(event.get("event_sequence", event.get("timestamp_ns", 0)))
