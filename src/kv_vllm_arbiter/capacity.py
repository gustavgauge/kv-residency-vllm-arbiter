"""Small contract helpers for expected active/resident capacity behavior."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapacityCase:
    """A capacity-boundary case for active/resident KV arbitration."""

    resident_blocks: int
    active_live_blocks: int
    usable_blocks: int

    @property
    def total_required(self) -> int:
        return self.resident_blocks + self.active_live_blocks

    @property
    def headroom_after_resident(self) -> int:
        return self.usable_blocks - self.resident_blocks


@dataclass(frozen=True)
class PolicyOutcome:
    """Expected semantic outcome for a policy in a capacity case."""

    policy: str
    resident_preserved: bool
    active_served: bool
    active_reusable: bool
    arbiter_action: str
    explanation: str


def fits(case: CapacityCase) -> bool:
    """Return whether resident and active KV fit in the usable pool."""

    return case.total_required <= case.usable_blocks


def classify_policy(policy: str, case: CapacityCase) -> PolicyOutcome:
    """Classify the expected semantic behavior for the starter policies.

    This is not a vLLM simulator. It is an expected-behavior oracle for the
    initial experiment matrix.
    """

    feasible = fits(case)

    if policy == "native":
        if feasible:
            return PolicyOutcome(
                policy=policy,
                resident_preserved=True,
                active_served=True,
                active_reusable=True,
                arbiter_action="serve_active_preserve_resident",
                explanation="resident and active KV fit",
            )
        return PolicyOutcome(
            policy=policy,
            resident_preserved=False,
            active_served=True,
            active_reusable=True,
            arbiter_action="serve_active_evict_resident",
            explanation="active allocation consumes resident victims without claim-level reporting",
        )

    if policy == "write_no_admit":
        if feasible:
            return PolicyOutcome(
                policy=policy,
                resident_preserved=True,
                active_served=True,
                active_reusable=False,
                arbiter_action="serve_active_no_admit",
                explanation="active KV fits but is not admitted for future reuse",
            )
        return PolicyOutcome(
            policy=policy,
            resident_preserved=False,
            active_served=True,
            active_reusable=False,
            arbiter_action="serve_active_no_admit_evict_resident",
            explanation="no-admit blocks future reuse but not active live pressure",
        )

    if policy in {"hard_resident_exclude", "resident_reserve"}:
        if feasible:
            return PolicyOutcome(
                policy=policy,
                resident_preserved=True,
                active_served=True,
                active_reusable=True,
                arbiter_action="serve_active_preserve_resident",
                explanation="protected residents and active KV fit",
            )
        return PolicyOutcome(
            policy=policy,
            resident_preserved=True,
            active_served=False,
            active_reusable=False,
            arbiter_action="capacity_required",
            explanation="protected residents leave insufficient active headroom",
        )

    if policy == "active_deferral":
        if feasible:
            return PolicyOutcome(
                policy=policy,
                resident_preserved=True,
                active_served=True,
                active_reusable=True,
                arbiter_action="serve_active_preserve_resident",
                explanation="no deferral required when resident and active fit",
            )
        return PolicyOutcome(
            policy=policy,
            resident_preserved=True,
            active_served=False,
            active_reusable=False,
            arbiter_action="defer_active",
            explanation="active work must wait for resident-safe headroom",
        )

    if policy == "active_refusal":
        if feasible:
            return PolicyOutcome(
                policy=policy,
                resident_preserved=True,
                active_served=True,
                active_reusable=True,
                arbiter_action="serve_active_preserve_resident",
                explanation="no refusal required when resident and active fit",
            )
        return PolicyOutcome(
            policy=policy,
            resident_preserved=True,
            active_served=False,
            active_reusable=False,
            arbiter_action="refuse_active",
            explanation="active work is refused under protected resident claims",
        )

    raise ValueError(f"unknown policy: {policy}")
