"""Materialization predicates used by the vLLM arbiter artifact."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class LeadingPrefixEvaluation:
    """Result of evaluating a leading-prefix materialization predicate."""

    required_blocks: int
    surviving_blocks: int
    leading_blocks: int
    materialized: bool

    def to_record(self) -> dict[str, int | bool | str]:
        return {
            "predicate": "leading_prefix_at_least",
            "required_blocks": self.required_blocks,
            "surviving_blocks": self.surviving_blocks,
            "leading_blocks": self.leading_blocks,
            "materialized": self.materialized,
        }


def leading_prefix_length(surviving_positions: Iterable[int]) -> int:
    """Return the contiguous prefix length starting at logical block 0."""

    surviving = {int(position) for position in surviving_positions}
    leading = 0
    while leading in surviving:
        leading += 1
    return leading


def evaluate_leading_prefix(
    surviving_positions: Iterable[int], required_blocks: int
) -> LeadingPrefixEvaluation:
    """Evaluate whether surviving logical positions satisfy a prefix claim."""

    surviving = {int(position) for position in surviving_positions}
    required = int(required_blocks)
    if required < 0:
        raise ValueError("required_blocks must be non-negative")
    leading = leading_prefix_length(surviving)
    return LeadingPrefixEvaluation(
        required_blocks=required,
        surviving_blocks=len(surviving),
        leading_blocks=leading,
        materialized=leading >= required,
    )
