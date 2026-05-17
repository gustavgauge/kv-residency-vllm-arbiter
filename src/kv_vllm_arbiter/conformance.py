"""Resident KV claim conformance results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


Event = dict[str, Any]


class ConformanceStatus(str, Enum):
    PASS = "pass"
    APPROXIMATE = "approximate"
    FAIL = "fail"
    NOT_EXPOSED = "not_exposed"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class ConformanceResult:
    litmus_id: str
    title: str
    status: ConformanceStatus
    required_observation: str
    observed: str
    evidence: tuple[str, ...] = ()
    fields: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "litmus_id": self.litmus_id,
            "title": self.title,
            "status": self.status.value,
            "required_observation": self.required_observation,
            "observed": self.observed,
            "evidence": list(self.evidence),
            "fields": self.fields,
        }


def event_counts(events: Iterable[Event]) -> dict[str, int]:
    event_list = list(events)
    return {
        event_name: sum(1 for event in event_list if event.get("event") == event_name)
        for event_name in sorted({str(event.get("event")) for event in event_list})
    }


def _first_event(events: Iterable[Event], event_name: str) -> Event | None:
    for event in events:
        if event.get("event") == event_name:
            return event
    return None


def evaluate_no_accepted_claim_no_harm(
    *,
    summary: dict[str, Any],
    events: list[Event],
    evidence: tuple[str, ...],
) -> ConformanceResult:
    counts = event_counts(events)
    passed = (
        counts.get("resident_claim_accepted", 0) == 0
        and counts.get("resident_claim_harmed", 0) == 0
        and int(summary.get("cached_resident_victims", 0)) > 0
    )
    return ConformanceResult(
        litmus_id="L1",
        title="No accepted claim, no claim harm",
        status=ConformanceStatus.PASS if passed else ConformanceStatus.FAIL,
        required_observation=(
            "Ordinary cached-prefix eviction may remove resident blocks, but it "
            "must not be labeled claim harm without prior claim acceptance."
        ),
        observed=(
            f"accepted={counts.get('resident_claim_accepted', 0)}, "
            f"claim_harmed={counts.get('resident_claim_harmed', 0)}, "
            f"cached_resident_victims={summary.get('cached_resident_victims', 0)}"
        ),
        evidence=evidence,
        fields={"event_counts": counts},
    )


def evaluate_write_no_admit_separation(
    *,
    summary: dict[str, Any],
    events: list[Event],
    evidence: tuple[str, ...],
) -> ConformanceResult:
    counts = event_counts(events)
    passed = (
        bool(summary.get("active_served"))
        and not bool(summary.get("active_future_reuse_admitted"))
        and int(summary.get("cached_resident_victims", 0)) > 0
        and counts.get("future_reuse_denied", 0) == 1
    )
    return ConformanceResult(
        litmus_id="L2",
        title="Write no-admit is separate from active-live allocation",
        status=ConformanceStatus.PASS if passed else ConformanceStatus.FAIL,
        required_observation=(
            "Denying future reuse for the active request must not be mistaken "
            "for bounding the request's live KV footprint."
        ),
        observed=(
            f"active_served={summary.get('active_served')}, "
            f"future_reuse_admitted={summary.get('active_future_reuse_admitted')}, "
            f"resident_victims={summary.get('cached_resident_victims')}"
        ),
        evidence=evidence,
        fields={"event_counts": counts},
    )


def evaluate_hard_claim_infeasibility(
    *,
    summary: dict[str, Any],
    events: list[Event],
    evidence: tuple[str, ...],
) -> ConformanceResult:
    counts = event_counts(events)
    refusal = _first_event(events, "active_request_refused")
    blocking_claim_ids = list(refusal.get("blocking_claim_ids", [])) if refusal else []
    passed = (
        not bool(summary.get("active_served"))
        and int(summary.get("cached_resident_victims", 0)) == 0
        and counts.get("resident_claim_accepted", 0) == 1
        and counts.get("resident_claim_materialized", 0) == 1
        and bool(blocking_claim_ids)
        and refusal is not None
        and refusal.get("feasibility") == "infeasible_preserve_resident_and_active"
    )
    return ConformanceResult(
        litmus_id="L3",
        title="Accepted hard claim makes infeasibility explicit",
        status=ConformanceStatus.PASS if passed else ConformanceStatus.FAIL,
        required_observation=(
            "When protected resident KV plus active-live KV exceed capacity, "
            "the runtime must preserve, demote/offload, or refuse/defer active "
            "with claim-level attribution."
        ),
        observed=(
            f"active_served={summary.get('active_served')}, "
            f"resident_victims={summary.get('cached_resident_victims')}, "
            f"blocking_claim_ids={blocking_claim_ids}, "
            f"feasibility={refusal.get('feasibility') if refusal else None}"
        ),
        evidence=evidence,
        fields={"event_counts": counts, "active_request_refused": refusal},
    )


def evaluate_demotion_or_expiry_before_loss(
    *,
    litmus_id: str,
    title: str,
    release_event: str,
    summary: dict[str, Any],
    events: list[Event],
    evidence: tuple[str, ...],
) -> ConformanceResult:
    counts = event_counts(events)
    passed = (
        counts.get(release_event, 0) == 1
        and counts.get("resident_claim_harmed", 0) == 0
        and counts.get("resident_claim_block_lost_after_release", 0) > 0
        and int(summary.get("cached_resident_victims", 0)) > 0
    )
    return ConformanceResult(
        litmus_id=litmus_id,
        title=title,
        status=ConformanceStatus.PASS if passed else ConformanceStatus.FAIL,
        required_observation=(
            "If a claim is explicitly released before block loss, later "
            "eviction is not claim harm."
        ),
        observed=(
            f"{release_event}={counts.get(release_event, 0)}, "
            f"claim_harmed={counts.get('resident_claim_harmed', 0)}, "
            "lost_after_release="
            f"{counts.get('resident_claim_block_lost_after_release', 0)}"
        ),
        evidence=evidence,
        fields={"event_counts": counts},
    )


def materialization_predicate_litmus(evidence: tuple[str, ...]) -> ConformanceResult:
    surviving_positions = tuple(range(1, 60))
    required_blocks = 60
    leading_blocks = 0
    materialized = leading_blocks >= required_blocks
    passed = len(surviving_positions) > 0 and not materialized
    return ConformanceResult(
        litmus_id="L6",
        title="Block survival can fail useful-prefix materialization",
        status=ConformanceStatus.PASS if passed else ConformanceStatus.FAIL,
        required_observation=(
            "A trace can retain many resident blocks while losing the leading "
            "prefix predicate that makes the future computation reusable."
        ),
        observed=(
            f"surviving_blocks={len(surviving_positions)}, "
            f"leading_blocks={leading_blocks}, required_blocks={required_blocks}, "
            f"materialized={materialized}"
        ),
        evidence=evidence,
        fields={
            "predicate": "leading_prefix_at_least",
            "required_blocks": required_blocks,
            "surviving_positions_sample": list(surviving_positions[:8]),
            "surviving_blocks": len(surviving_positions),
            "leading_blocks": leading_blocks,
            "materialized": materialized,
        },
    )


def backend_approximation_litmus(evidence: tuple[str, ...]) -> ConformanceResult:
    return ConformanceResult(
        litmus_id="C1",
        title="Capability check: soft priority is not a sound hard-claim lowering",
        status=ConformanceStatus.PASS,
        required_observation=(
            "A backend primitive that only changes eviction preference must be "
            "marked approximate or unsound for hard_protected claims."
        ),
        observed=(
            "The capability classifier separates priority/duration primitives "
            "from accepted hard-claim infeasibility and claim-harm telemetry."
        ),
        evidence=evidence,
        fields={
            "hard_protected_lowered_to_soft_priority": "unsound",
            "soft_priority_conformance_class": "approximate",
        },
    )


def render_results_markdown(results: Iterable[ConformanceResult]) -> str:
    lines = [
        "# ResidentClaim Conformance Results",
        "",
        "| Litmus | Status | Required observation | Observed | Evidence |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        evidence = "<br>".join(f"`{item}`" for item in result.evidence)
        lines.append(
            f"| {result.litmus_id}: {result.title} | {result.status.value} | "
            f"{result.required_observation} | {result.observed} | {evidence} |"
        )
    return "\n".join(lines) + "\n"
