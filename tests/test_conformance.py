from kv_vllm_arbiter.conformance import (
    ConformanceStatus,
    evaluate_demotion_or_expiry_before_loss,
    evaluate_hard_claim_infeasibility,
    evaluate_no_accepted_claim_no_harm,
    evaluate_write_no_admit_separation,
    materialization_predicate_litmus,
)


def test_no_accepted_claim_no_harm_requires_absent_acceptance() -> None:
    result = evaluate_no_accepted_claim_no_harm(
        summary={"cached_resident_victims": 3},
        events=[
            {"event": "resident_block_materialized"},
            {"event": "allocation_victim_selected"},
        ],
        evidence=("trace.jsonl",),
    )

    assert result.status == ConformanceStatus.PASS


def test_write_no_admit_litmus_requires_active_served_and_resident_loss() -> None:
    result = evaluate_write_no_admit_separation(
        summary={
            "active_served": True,
            "active_future_reuse_admitted": False,
            "cached_resident_victims": 50,
        },
        events=[{"event": "future_reuse_denied"}],
        evidence=("trace.jsonl",),
    )

    assert result.status == ConformanceStatus.PASS


def test_hard_claim_litmus_requires_direct_blocking_claim_attribution() -> None:
    result = evaluate_hard_claim_infeasibility(
        summary={"active_served": False, "cached_resident_victims": 0},
        events=[
            {"event": "resident_claim_accepted"},
            {"event": "resident_claim_materialized"},
            {
                "event": "active_request_refused",
                "request_id": "active",
                "blocking_claim_ids": ["claim:resident"],
                "feasibility": "infeasible_preserve_resident_and_active",
            },
        ],
        evidence=("trace.jsonl",),
    )

    assert result.status == ConformanceStatus.PASS
    assert result.fields["active_request_refused"]["blocking_claim_ids"] == [
        "claim:resident"
    ]


def test_hard_claim_litmus_fails_without_blocking_claim_attribution() -> None:
    result = evaluate_hard_claim_infeasibility(
        summary={"active_served": False, "cached_resident_victims": 0},
        events=[
            {"event": "resident_claim_accepted"},
            {"event": "resident_claim_materialized"},
            {
                "event": "active_request_refused",
                "request_id": "active",
                "feasibility": "infeasible_preserve_resident_and_active",
            },
        ],
        evidence=("trace.jsonl",),
    )

    assert result.status == ConformanceStatus.FAIL


def test_demote_before_loss_rejects_post_release_harm() -> None:
    result = evaluate_demotion_or_expiry_before_loss(
        litmus_id="L4",
        title="Demotion precedes loss",
        release_event="resident_claim_demoted",
        summary={"cached_resident_victims": 50},
        events=[
            {"event": "resident_claim_demoted"},
            {"event": "resident_claim_block_lost_after_release"},
        ],
        evidence=("trace.jsonl",),
    )

    assert result.status == ConformanceStatus.PASS


def test_materialization_litmus_models_block_survival_without_value() -> None:
    result = materialization_predicate_litmus(evidence=("test.py",))

    assert result.status == ConformanceStatus.PASS
    assert result.fields["surviving_blocks"] > 0
    assert result.fields["materialized"] is False
