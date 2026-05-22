from kv_vllm_arbiter.offload_lifecycle import (
    build_reference_trace,
    evaluate_offload_lifecycle_events,
)


def missing_for(scenario: str) -> list[str]:
    events = build_reference_trace(scenario)
    result = evaluate_offload_lifecycle_events(events)
    return result.gate_summary["reference_missing_requirements"]


def test_positive_offload_lifecycle_bundle_passes_reference_gate() -> None:
    events = build_reference_trace("positive_bundle")

    result = evaluate_offload_lifecycle_events(events)

    assert result.passes_reference_gate
    assert result.success_generation == 1
    assert result.failure_generation == 2
    assert result.event_counts["resident_claim_offloaded"] == 2
    assert result.event_counts["resident_claim_restored"] == 1
    assert result.event_counts["resident_claim_restoration_failed"] == 1


def test_generic_substrate_cannot_satisfy_claim_lifecycle() -> None:
    missing = missing_for("generic_substrate")

    assert "pre_registered_accepted_claim" in missing
    assert "offload_restorability" in missing
    assert "restoration_failure_outcome" in missing


def test_claim_joined_offload_without_restore_fails() -> None:
    missing = missing_for("claim_offload_no_restore")

    assert "offload_restorability" in missing
    assert "restoration_failure_outcome" in missing


def test_restore_after_reuse_fails_ordered_restorability() -> None:
    missing = missing_for("restore_after_reuse")

    assert "offload_restorability" in missing
    assert "ordered_lifecycle_events" in missing


def test_restoration_failure_outcome_must_match_claim_id() -> None:
    missing = missing_for("wrong_claim_failure_outcome")

    assert "restoration_failure_outcome" in missing
    assert "ordered_lifecycle_events" in missing


def test_missing_token_map_identity_fails() -> None:
    missing = missing_for("missing_identity")

    assert "fixed_cache_identity_and_deterministic_request_token_map" in missing


def test_post_hoc_claim_naming_fails() -> None:
    missing = missing_for("post_hoc_claim_naming")

    assert "pre_registered_accepted_claim" in missing


def test_fallback_recompute_is_not_restoration_from_offload() -> None:
    missing = missing_for("fallback_recompute")

    assert "offload_restorability" in missing
