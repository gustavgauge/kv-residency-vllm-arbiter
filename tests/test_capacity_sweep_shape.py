from kv_vllm_arbiter.trace_summary import classify_active_resident_outcome


def test_hard_exclude_transition_shape_from_telemetry() -> None:
    refused = classify_active_resident_outcome(
        [
            {
                "event": "resident_block_materialized",
                "run_id": "below",
                "policy": "hard_resident_exclude",
                "usable_blocks": 120,
                "request_id": "resident",
                "physical_block_id": 1,
                "logical_block_position": 0,
                "is_protected_resident": True,
            },
            {
                "event": "active_request_refused",
                "run_id": "below",
                "policy": "hard_resident_exclude",
                "usable_blocks": 120,
                "request_id": "active",
            },
        ]
    )
    served = classify_active_resident_outcome(
        [
            {
                "event": "resident_block_materialized",
                "run_id": "at-boundary",
                "policy": "hard_resident_exclude",
                "usable_blocks": 130,
                "request_id": "resident",
                "physical_block_id": 1,
                "logical_block_position": 0,
                "is_protected_resident": True,
            },
            {
                "event": "allocation_victim_selected",
                "run_id": "at-boundary",
                "policy": "hard_resident_exclude",
                "usable_blocks": 130,
                "request_id": "active",
                "physical_block_id": 61,
                "victim_reason": "free_uncached",
            },
        ]
    )

    assert refused.active_action == "active_refused"
    assert refused.resident_preserved
    assert served.active_action == "active_served"
    assert served.resident_preserved
