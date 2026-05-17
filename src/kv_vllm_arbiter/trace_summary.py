"""Summarize active/resident KV telemetry traces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


Event = dict[str, Any]


@dataclass(frozen=True)
class NativeHarmSummary:
    """Causal accounting for native allocation harm to resident reusable KV."""

    run_id: str
    policy: str
    usable_blocks: int
    resident_materialized: int
    active_allocation_victims: int
    cached_resident_victims: int
    remaining_cached_resident_blocks: int
    harmed_logical_block_positions: tuple[int, ...]

    @property
    def leading_blocks_survived(self) -> int:
        harmed = set(self.harmed_logical_block_positions)
        position = 0
        while position not in harmed and position < self.resident_materialized:
            position += 1
        return position

    @property
    def value_lost_blocks(self) -> int:
        return len(self.harmed_logical_block_positions)

    def to_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "policy": self.policy,
            "usable_blocks": self.usable_blocks,
            "resident_materialized": self.resident_materialized,
            "active_allocation_victims": self.active_allocation_victims,
            "cached_resident_victims": self.cached_resident_victims,
            "remaining_cached_resident_blocks": self.remaining_cached_resident_blocks,
            "harmed_logical_block_positions": list(
                self.harmed_logical_block_positions
            ),
            "leading_blocks_survived": self.leading_blocks_survived,
            "value_lost_blocks": self.value_lost_blocks,
        }


@dataclass(frozen=True)
class ActiveResidentOutcome:
    """Machine-classified active/resident outcome from telemetry events."""

    run_id: str
    policy: str
    usable_blocks: int
    active_action: str
    active_served: bool
    active_future_reuse_admitted: bool
    resident_preserved: bool
    cached_resident_victims: int
    protected_resident_blocks: int
    blocking_claim_ids: tuple[str, ...] = ()
    feasibility: str | None = None
    capacity_shortfall_blocks: int = 0

    def to_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "policy": self.policy,
            "usable_blocks": self.usable_blocks,
            "active_action": self.active_action,
            "active_served": self.active_served,
            "active_future_reuse_admitted": self.active_future_reuse_admitted,
            "resident_preserved": self.resident_preserved,
            "cached_resident_victims": self.cached_resident_victims,
            "protected_resident_blocks": self.protected_resident_blocks,
            "blocking_claim_ids": list(self.blocking_claim_ids),
            "feasibility": self.feasibility,
            "capacity_shortfall_blocks": self.capacity_shortfall_blocks,
        }


def load_jsonl(path: Path) -> list[Event]:
    """Load telemetry events from a JSON Lines file."""

    return [json.loads(line) for line in path.read_text().splitlines() if line]


def summarize_native_harm(events: Iterable[Event]) -> NativeHarmSummary:
    """Summarize resident reusable KV harm from native allocation events."""

    materialized_by_block: dict[int, Event] = {}
    active_victims: list[Event] = []
    run_id = "unknown"
    policy = "unknown"
    usable_blocks = 0

    for event in events:
        run_id = event.get("run_id", run_id)
        policy = event.get("policy", policy)
        usable_blocks = int(event.get("usable_blocks", usable_blocks))

        if event.get("event") == "resident_block_materialized":
            materialized_by_block[int(event["physical_block_id"])] = event
        elif (
            event.get("event") == "allocation_victim_selected"
            and event.get("request_id") == "active"
        ):
            active_victims.append(event)

    harmed_positions = []
    for victim in active_victims:
        block_id = int(victim["physical_block_id"])
        if (
            victim.get("victim_reason") == "cached_prefix_reuse"
            and block_id in materialized_by_block
        ):
            harmed_positions.append(
                int(materialized_by_block[block_id]["logical_block_position"])
            )

    return NativeHarmSummary(
        run_id=run_id,
        policy=policy,
        usable_blocks=usable_blocks,
        resident_materialized=len(materialized_by_block),
        active_allocation_victims=len(active_victims),
        cached_resident_victims=len(harmed_positions),
        remaining_cached_resident_blocks=(
            len(materialized_by_block) - len(harmed_positions)
        ),
        harmed_logical_block_positions=tuple(sorted(harmed_positions)),
    )


def classify_active_resident_outcome(events: Iterable[Event]) -> ActiveResidentOutcome:
    """Classify active/resident behavior from structured telemetry."""

    event_list = list(events)
    harm = summarize_native_harm(event_list)
    active_events = [
        event for event in event_list if event.get("request_id") == "active"
    ]
    protected_blocks = {
        int(event["physical_block_id"])
        for event in event_list
        if event.get("event") == "resident_block_materialized"
        and event.get("is_protected_resident") is True
    }

    active_action = "unknown"
    conflict_event: Event | None = None
    active_served = any(
        event.get("event") == "active_request_admitted" for event in active_events
    )
    active_future_reuse_admitted = any(
        event.get("event") == "future_reuse_admitted" for event in active_events
    )

    for event in active_events:
        if event.get("event") in {
            "active_request_refused",
            "active_request_deferred",
        }:
            conflict_event = event
            break

    if any(event.get("event") == "active_request_refused" for event in active_events):
        active_action = "active_refused"
        active_served = False
    elif any(
        event.get("event") == "active_request_deferred" for event in active_events
    ):
        active_action = "active_deferred"
        active_served = False
    elif active_served or any(
        event.get("event") == "allocation_victim_selected"
        for event in active_events
    ):
        active_action = "active_served"
        active_served = True

    if any(event.get("event") == "future_reuse_denied" for event in active_events):
        active_future_reuse_admitted = False

    blocking_claim_ids: tuple[str, ...] = ()
    feasibility: str | None = None
    capacity_shortfall_blocks = 0
    if conflict_event is not None:
        blocking_claim_ids = tuple(
            sorted(str(item) for item in conflict_event.get("blocking_claim_ids", []))
        )
        feasibility = conflict_event.get("feasibility")
        capacity_shortfall_blocks = int(
            conflict_event.get("capacity_shortfall_blocks", 0)
        )

    return ActiveResidentOutcome(
        run_id=harm.run_id,
        policy=harm.policy,
        usable_blocks=harm.usable_blocks,
        active_action=active_action,
        active_served=active_served,
        active_future_reuse_admitted=active_future_reuse_admitted,
        resident_preserved=harm.cached_resident_victims == 0,
        cached_resident_victims=harm.cached_resident_victims,
        protected_resident_blocks=len(protected_blocks),
        blocking_claim_ids=blocking_claim_ids,
        feasibility=feasibility,
        capacity_shortfall_blocks=capacity_shortfall_blocks,
    )


def format_native_harm_markdown(summary: NativeHarmSummary) -> str:
    """Render a concise markdown interpretation of a native harm trace."""

    positions = ", ".join(str(pos) for pos in summary.harmed_logical_block_positions)
    return "\n".join(
        [
            f"# Native Active/Resident KV Harm Trace: {summary.run_id}",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| usable KV blocks | {summary.usable_blocks} |",
            f"| resident reusable KV blocks materialized | {summary.resident_materialized} |",
            f"| active live KV allocation victims | {summary.active_allocation_victims} |",
            f"| resident reusable KV victims | {summary.cached_resident_victims} |",
            f"| remaining cached resident blocks | {summary.remaining_cached_resident_blocks} |",
            f"| leading resident blocks survived | {summary.leading_blocks_survived} |",
            f"| value lost, in blocks | {summary.value_lost_blocks} |",
            "",
            "Harmed logical resident block positions:",
            "",
            positions,
            "",
        ]
    )
