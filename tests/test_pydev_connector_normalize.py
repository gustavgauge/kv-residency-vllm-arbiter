import json
from pathlib import Path

from kv_vllm_arbiter.pydev_connector_failure import evaluate_pydev_connector_events
from kv_vllm_arbiter.pydev_connector_normalize import (
    Provenance,
    aggregate_normalized,
    normalize_summary,
)


CLAIM = "claim:test"


def failure_events() -> list[dict]:
    return [
        {
            "event": "request_initialized",
            "event_sequence": 1,
            "monotonic_ns": 1_000,
            "claim_id": CLAIM,
            "predicate_id": "predicate:test",
        },
        {
            "event": "offload_store_job_created",
            "event_sequence": 2,
            "monotonic_ns": 2_000,
            "claim_id": CLAIM,
            "job_id": 0,
        },
        {
            "event": "offload_worker_transfer_finished",
            "event_sequence": 3,
            "monotonic_ns": 3_000,
            "claim_id": CLAIM,
            "job_id": 0,
            "transfer_type": ["GPU", "CPU"],
            "transfer_size": 32,
            "success": True,
        },
        {
            "event": "offload_lookup_result",
            "event_sequence": 4,
            "monotonic_ns": 4_000,
            "claim_id": CLAIM,
            "num_hit_tokens": 8,
            "will_load_async": True,
        },
        {
            "event": "resident_claim_restore_required",
            "event_sequence": 5,
            "monotonic_ns": 5_000,
            "claim_id": CLAIM,
        },
        {
            "event": "offload_load_job_created",
            "event_sequence": 6,
            "monotonic_ns": 6_000,
            "claim_id": CLAIM,
            "job_id": 1,
        },
        {
            "event": "offload_worker_transfer_finished",
            "event_sequence": 7,
            "monotonic_ns": 7_000,
            "claim_id": CLAIM,
            "job_id": 1,
            "transfer_type": ["CPU", "GPU"],
            "transfer_size": 32,
            "success": False,
            "failure_injection_flag": True,
        },
        {
            "event": "offload_load_job_failed",
            "event_sequence": 8,
            "monotonic_ns": 8_000,
            "claim_id": CLAIM,
            "job_id": 1,
            "is_store": False,
        },
        {
            "event": "resident_claim_restoration_failed",
            "event_sequence": 9,
            "monotonic_ns": 9_000,
            "claim_id": CLAIM,
            "job_id": 1,
            "outcome_claim_id": CLAIM,
            "controlled_restoration_unavailable": True,
            "failure_injection_flag": True,
        },
        {
            "event": "active_request_refused",
            "event_sequence": 10,
            "monotonic_ns": 10_000,
            "claim_id": CLAIM,
            "job_id": 1,
            "outcome_claim_id": CLAIM,
            "blocking_claim_ids": [CLAIM],
        },
    ]


def test_normalized_summary_records_required_audit_fields(tmp_path: Path) -> None:
    events = failure_events()
    evaluation = evaluate_pydev_connector_events(events, expected_claim_id=CLAIM)
    event_path = tmp_path / "vllm_runtime_events.jsonl"
    event_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "scenario": "claimed_load_failure",
                "run_id": "run:rep-001",
                "model": "unit-model",
                "python": "/unit/python",
                "runtime": {"device0": "unit-gpu"},
                "event_path": str(event_path),
                "event_count": len(events),
                "event_bytes": event_path.stat().st_size,
                "request_records": [
                    {"role": "resident", "wall_latency_s": 0.1, "num_output_tokens": 2},
                    {
                        "role": "reuse",
                        "wall_latency_s": 0.01,
                        "num_cached_tokens": 0,
                        "num_output_tokens": 0,
                        "connector_outcome": "active_request_refused",
                    },
                ],
                "evaluation": evaluation.to_record(),
                "transfer_metrics": {
                    "worker_transfer_count": 2,
                    "directions": [["GPU", "CPU"], ["CPU", "GPU"]],
                    "worker_transfer_sizes": [32, 32],
                },
            }
        ),
        encoding="utf-8",
    )

    normalized = normalize_summary(
        summary_path,
        provenance=Provenance(
            parent_commit="parent",
            artifact_commit="artifact",
            vllm_base_commit="base",
            vllm_patch_commits=[{"commit": "patch", "subject": "subject"}],
            runner_path="/runner",
        ),
        repetition_id="rep-001",
        run_set_id="unit",
    )

    assert normalized["scenario_id"] == "claimed_load_failure"
    assert normalized["failure_outcome_gate_result"]
    assert normalized["event_sequence_valid"]
    assert normalized["claim_id"] == CLAIM
    assert normalized["predicate_id"] == "predicate:test"
    assert normalized["transfer_bytes_total"] == 64
    assert normalized["failure_to_outcome_latency_ns"] == 2_000
    assert (
        normalized["restoration_failed_to_active_request_refused_latency_ns"] == 1_000
    )
    assert normalized["final_request_outcome_label"] == "active_request_refused"


def test_aggregate_normalized_reports_rates_and_stats() -> None:
    aggregate = aggregate_normalized(
        [
            {
                "scenario_id": "success_path",
                "observation_gate_result": True,
                "failure_outcome_gate_result": False,
                "event_sequence_valid": True,
                "final_request_outcome_label": "served",
                "resident_request_wall_time_s": 0.1,
                "reuse_request_wall_time_s": 0.2,
                "event_bytes": 100,
                "analyzer_runtime_ns": 10,
                "failure_to_outcome_latency_ns": None,
                "restoration_failed_to_active_request_refused_latency_ns": None,
                "reuse_cached_tokens": 8,
                "worker_transfer_count": 2,
                "transfer_bytes_total": 64,
            }
        ]
    )

    scenario = aggregate["scenarios"]["success_path"]
    assert scenario["runs"] == 1
    assert scenario["observation_gate_pass_rate"]["passed"] == 1
    assert scenario["failure_outcome_gate_pass_rate"]["passed"] == 0
    assert scenario["resident_wall_time_s"]["median"] == 0.1
