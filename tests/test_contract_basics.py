from kv_vllm_arbiter import ArbiterEvent, CapacityCase, classify_policy, fits


def test_capacity_boundary_fails_below_130_blocks() -> None:
    case = CapacityCase(resident_blocks=60, active_live_blocks=70, usable_blocks=80)

    assert not fits(case)
    assert case.total_required == 130
    assert case.headroom_after_resident == 20


def test_capacity_boundary_passes_at_130_blocks() -> None:
    case = CapacityCase(resident_blocks=60, active_live_blocks=70, usable_blocks=130)

    assert fits(case)
    assert case.headroom_after_resident == 70


def test_no_admit_does_not_preserve_residents_when_infeasible() -> None:
    case = CapacityCase(resident_blocks=60, active_live_blocks=70, usable_blocks=80)
    outcome = classify_policy("write_no_admit", case)

    assert outcome.active_served
    assert not outcome.active_reusable
    assert not outcome.resident_preserved
    assert outcome.arbiter_action == "serve_active_no_admit_evict_resident"


def test_hard_resident_exclusion_preserves_residents_by_not_serving_active() -> None:
    case = CapacityCase(resident_blocks=60, active_live_blocks=70, usable_blocks=80)
    outcome = classify_policy("hard_resident_exclude", case)

    assert outcome.resident_preserved
    assert not outcome.active_served
    assert outcome.arbiter_action == "capacity_required"


def test_telemetry_event_serializes_flat_json() -> None:
    event = ArbiterEvent(
        event="active_request_deferred",
        run_id="run",
        request_id="active",
        claim_id="resident",
        prefix_id="small_hot",
        policy="active_deferral",
        usable_blocks=80,
        fields={"arbiter_action": "defer_active", "active_live_blocks_required": 70},
    )

    encoded = event.to_json()

    assert '"event":"active_request_deferred"' in encoded
    assert '"arbiter_action":"defer_active"' in encoded
    assert '"active_live_blocks_required":70' in encoded
