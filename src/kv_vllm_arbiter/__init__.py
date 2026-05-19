"""Scaffolding for the vLLM active/resident KV arbiter prototype."""

from .capacity import CapacityCase, PolicyOutcome, classify_policy, fits
from .conformance import (
    ConformanceResult,
    ConformanceStatus,
    backend_approximation_litmus,
    evaluate_demotion_or_expiry_before_loss,
    evaluate_hard_claim_infeasibility,
    evaluate_no_accepted_claim_no_harm,
    evaluate_write_no_admit_separation,
    materialization_predicate_litmus,
    render_results_markdown,
)
from .materialization import (
    LeadingPrefixEvaluation,
    evaluate_leading_prefix,
    leading_prefix_length,
)
from .telemetry import ArbiterEvent
from .trace_summary import (
    ActiveResidentOutcome,
    NativeHarmSummary,
    classify_active_resident_outcome,
    summarize_native_harm,
)

__all__ = [
    "ArbiterEvent",
    "ActiveResidentOutcome",
    "CapacityCase",
    "ConformanceResult",
    "ConformanceStatus",
    "LeadingPrefixEvaluation",
    "NativeHarmSummary",
    "PolicyOutcome",
    "backend_approximation_litmus",
    "classify_policy",
    "classify_active_resident_outcome",
    "evaluate_demotion_or_expiry_before_loss",
    "evaluate_hard_claim_infeasibility",
    "evaluate_leading_prefix",
    "evaluate_no_accepted_claim_no_harm",
    "evaluate_write_no_admit_separation",
    "fits",
    "leading_prefix_length",
    "materialization_predicate_litmus",
    "render_results_markdown",
    "summarize_native_harm",
]
