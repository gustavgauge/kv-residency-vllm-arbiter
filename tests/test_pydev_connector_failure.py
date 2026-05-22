from kv_vllm_arbiter.pydev_connector_failure import evaluate_pydev_connector_events


CLAIM = "claim:test"


def base_success_events() -> list[dict]:
    return [
        {"event": "request_initialized", "event_sequence": 1, "claim_id": CLAIM},
        {
            "event": "offload_store_job_created",
            "event_sequence": 2,
            "claim_id": CLAIM,
            "job_id": 0,
        },
        {
            "event": "offload_worker_transfer_finished",
            "event_sequence": 3,
            "claim_id": CLAIM,
            "job_id": 0,
            "transfer_type": ["GPU", "CPU"],
            "success": True,
        },
        {
            "event": "offload_job_completed",
            "event_sequence": 4,
            "claim_id": CLAIM,
            "job_id": 0,
            "is_store": True,
        },
        {
            "event": "offload_lookup_result",
            "event_sequence": 5,
            "claim_id": CLAIM,
            "num_hit_tokens": 448,
            "will_load_async": True,
        },
        {
            "event": "resident_claim_restore_required",
            "event_sequence": 6,
            "claim_id": CLAIM,
        },
        {
            "event": "offload_load_job_created",
            "event_sequence": 7,
            "claim_id": CLAIM,
            "job_id": 1,
        },
        {
            "event": "offload_worker_transfer_finished",
            "event_sequence": 8,
            "claim_id": CLAIM,
            "job_id": 1,
            "transfer_type": ["CPU", "GPU"],
            "success": True,
        },
        {
            "event": "resident_claim_restored",
            "event_sequence": 9,
            "claim_id": CLAIM,
            "job_id": 1,
        },
        {
            "event": "offload_job_completed",
            "event_sequence": 10,
            "claim_id": CLAIM,
            "job_id": 1,
            "is_store": False,
        },
    ]


def failure_tail(
    start_sequence: int = 8,
    claim_id: str = CLAIM,
    *,
    scheduler_refusal: bool = True,
    connector_refusal: bool = True,
    outcome_type: str = "refusal",
) -> list[dict]:
    events = [
        {
            "event": "offload_worker_transfer_finished",
            "event_sequence": start_sequence,
            "claim_id": claim_id,
            "job_id": 1,
            "transfer_type": ["CPU", "GPU"],
            "success": False,
            "failure_injection_flag": True,
        },
        {
            "event": "scheduler_resident_claim_restoration_failed",
            "event_sequence": start_sequence + 1,
            "claim_id": claim_id,
            "outcome_claim_id": claim_id,
            "scheduler_side_failure_outcome": True,
            "scheduler_side_refusal": scheduler_refusal,
            "native_scheduler_admission_refusal": False,
            "finish_status": "FINISHED_ERROR",
            "finish_reason": "error",
            "blocking_claim_ids": [claim_id] if scheduler_refusal else [],
        },
    ]
    if scheduler_refusal:
        events.append(
            {
                "event": "scheduler_active_request_refused",
                "event_sequence": start_sequence + 2,
                "claim_id": claim_id,
                "outcome_claim_id": claim_id,
                "blocking_claim_ids": [claim_id],
                "scheduler_side_refusal": True,
                "native_scheduler_admission_refusal": False,
                "finish_status": "FINISHED_ERROR",
                "finish_reason": "error",
            }
        )
    termination_after = events[-1]["event_sequence"] + 1
    events.extend(
        [
            {
                "event": "offload_request_finished_pending_jobs",
                "event_sequence": termination_after,
                "claim_id": claim_id,
            },
            {
                "event": "offload_load_job_failed",
                "event_sequence": termination_after + 1,
                "claim_id": claim_id,
                "job_id": 1,
                "is_store": False,
            },
            {
                "event": "resident_claim_restoration_failed",
                "event_sequence": termination_after + 2,
                "claim_id": claim_id,
                "job_id": 1,
                "outcome_claim_id": claim_id,
                "controlled_restoration_unavailable": True,
                "failure_injection_flag": True,
                "claim_scoped_outcome_type": outcome_type,
            },
        ]
    )
    if connector_refusal:
        events.append(
            {
                "event": "active_request_refused",
                "event_sequence": termination_after + 3,
                "claim_id": claim_id,
                "job_id": 1,
                "outcome_claim_id": claim_id,
                "blocking_claim_ids": [claim_id],
            }
        )
    return events


def test_success_path_classifies_connector_observation() -> None:
    result = evaluate_pydev_connector_events(base_success_events())

    assert result.connector_observation_success
    assert not result.restoration_failure_outcome_success
    assert "controlled_cpu_to_gpu_load_failure" in result.gate_summary[
        "failure_missing_requirements"
    ]


def test_claimed_load_failure_requires_matching_refusal() -> None:
    events = base_success_events()[:7] + failure_tail()

    result = evaluate_pydev_connector_events(events)

    assert result.restoration_failure_outcome_success
    assert result.gate_summary["scheduler_side_failure_outcome_present"]
    assert result.gate_summary["scheduler_side_refusal_present"]
    assert result.gate_summary["scheduler_event_before_or_at_termination"]


def test_wrong_claim_failure_is_rejected() -> None:
    events = base_success_events()[:7] + failure_tail(claim_id="claim:wrong")

    result = evaluate_pydev_connector_events(events, expected_claim_id=CLAIM)

    assert not result.restoration_failure_outcome_success
    assert "controlled_cpu_to_gpu_load_failure" in result.gate_summary[
        "failure_missing_requirements"
    ]


def test_unclaimed_failure_is_not_claim_scoped() -> None:
    events = [
        {
            "event": "offload_worker_transfer_finished",
            "event_sequence": 1,
            "transfer_type": ["CPU", "GPU"],
            "success": False,
        },
        {
            "event": "offload_load_job_failed",
            "event_sequence": 2,
            "is_store": False,
        },
    ]

    result = evaluate_pydev_connector_events(events)

    assert not result.restoration_failure_outcome_success
    assert result.gate_summary["controls"]["unclaimed_failure_rejected"]


def test_fallback_recompute_without_refusal_is_rejected() -> None:
    events = base_success_events()[:7] + failure_tail(
        scheduler_refusal=False,
        connector_refusal=False,
        outcome_type="fallback_recompute_without_claim_satisfaction",
    )

    result = evaluate_pydev_connector_events(events)

    assert not result.restoration_failure_outcome_success
    assert result.gate_summary["controls"]["fallback_recompute_rejected"]
