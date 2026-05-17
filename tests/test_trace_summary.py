from kv_vllm_arbiter.trace_summary import (
    classify_active_resident_outcome,
    format_native_harm_markdown,
    summarize_native_harm,
)


def test_summarize_native_harm_accounts_for_resident_victims() -> None:
    events = [
        {
            "event": "resident_block_materialized",
            "run_id": "run",
            "policy": "native",
            "usable_blocks": 4,
            "request_id": "resident",
            "physical_block_id": 1,
            "logical_block_position": 0,
        },
        {
            "event": "resident_block_materialized",
            "run_id": "run",
            "policy": "native",
            "usable_blocks": 4,
            "request_id": "resident",
            "physical_block_id": 2,
            "logical_block_position": 1,
        },
        {
            "event": "allocation_victim_selected",
            "run_id": "run",
            "policy": "native",
            "usable_blocks": 4,
            "request_id": "active",
            "physical_block_id": 3,
            "victim_reason": "free_uncached",
        },
        {
            "event": "allocation_victim_selected",
            "run_id": "run",
            "policy": "native",
            "usable_blocks": 4,
            "request_id": "active",
            "physical_block_id": 2,
            "victim_reason": "cached_prefix_reuse",
        },
    ]

    summary = summarize_native_harm(events)

    assert summary.resident_materialized == 2
    assert summary.active_allocation_victims == 2
    assert summary.cached_resident_victims == 1
    assert summary.remaining_cached_resident_blocks == 1
    assert summary.harmed_logical_block_positions == (1,)
    assert summary.leading_blocks_survived == 1
    assert summary.value_lost_blocks == 1


def test_format_native_harm_markdown_includes_key_metrics() -> None:
    summary = summarize_native_harm(
        [
            {
                "event": "resident_block_materialized",
                "run_id": "run",
                "policy": "native",
                "usable_blocks": 4,
                "request_id": "resident",
                "physical_block_id": 1,
                "logical_block_position": 0,
            },
            {
                "event": "allocation_victim_selected",
                "run_id": "run",
                "policy": "native",
                "usable_blocks": 4,
                "request_id": "active",
                "physical_block_id": 1,
                "victim_reason": "cached_prefix_reuse",
            },
        ]
    )

    markdown = format_native_harm_markdown(summary)

    assert "resident reusable KV victims | 1" in markdown
    assert "leading resident blocks survived | 0" in markdown


def test_classify_active_resident_outcome_refused_preserves_residents() -> None:
    outcome = classify_active_resident_outcome(
        [
            {
                "event": "resident_block_materialized",
                "run_id": "run",
                "policy": "hard_resident_exclude",
                "usable_blocks": 80,
                "request_id": "resident",
                "physical_block_id": 1,
                "logical_block_position": 0,
                "is_protected_resident": True,
            },
            {
                "event": "active_request_refused",
                "run_id": "run",
                "policy": "hard_resident_exclude",
                "usable_blocks": 80,
                "request_id": "active",
                "arbiter_action": "capacity_required",
                "blocking_claim_ids": ["claim:resident"],
                "feasibility": "infeasible_preserve_resident_and_active",
                "capacity_shortfall_blocks": 50,
            },
        ]
    )

    assert outcome.active_action == "active_refused"
    assert not outcome.active_served
    assert outcome.resident_preserved
    assert outcome.protected_resident_blocks == 1
    assert outcome.blocking_claim_ids == ("claim:resident",)
    assert outcome.feasibility == "infeasible_preserve_resident_and_active"
    assert outcome.capacity_shortfall_blocks == 50


def test_classify_active_resident_outcome_deferred_is_scheduler_visible() -> None:
    outcome = classify_active_resident_outcome(
        [
            {
                "event": "active_request_deferred",
                "run_id": "run",
                "policy": "hard_resident_exclude",
                "usable_blocks": 80,
                "request_id": "active",
                "arbiter_action": "scheduler_full_sequence_gate",
            }
        ]
    )

    assert outcome.active_action == "active_deferred"
    assert not outcome.active_served
