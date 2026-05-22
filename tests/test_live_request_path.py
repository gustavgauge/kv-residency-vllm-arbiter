from kv_vllm_arbiter.live_request_path import (
    INSTRUMENTATION_SCOPE,
    LiveRequestRecord,
    build_request_coupled_trace,
    evaluate_request_coupled_trace,
)


def sample_records() -> list[LiveRequestRecord]:
    return [
        LiveRequestRecord(
            role="resident",
            request_id="0",
            wall_latency_s=0.2,
            ttft_s=0.05,
            num_prompt_tokens=144,
            num_cached_tokens=0,
            num_output_tokens=8,
        ),
        LiveRequestRecord(
            role="reuse",
            request_id="1",
            wall_latency_s=0.12,
            ttft_s=0.03,
            num_prompt_tokens=144,
            num_cached_tokens=128,
            num_output_tokens=8,
        ),
        LiveRequestRecord(
            role="failure",
            request_id="2",
            wall_latency_s=0.001,
            status="controlled_refusal_by_harness",
        ),
    ]


def test_request_coupled_positive_trace_preserves_live_ids() -> None:
    events = build_request_coupled_trace(
        sample_records(),
        run_id="test-live-path",
        emit_events=True,
    )

    result = evaluate_request_coupled_trace(events)

    assert result["passes_reference_gate"]
    assert {event["request_id"] for event in events} == {"0", "1", "2"}
    assert all(event["instrumentation_scope"] == INSTRUMENTATION_SCOPE for event in events)
    assert "claim_accepted" in result["contract_event_order"]
    assert "reuse_consumed_restored_state" in result["contract_event_order"]
    assert "active_request_refused" in result["contract_event_order"]


def test_event_emission_disabled_does_not_pass_gate() -> None:
    events = build_request_coupled_trace(
        sample_records(),
        run_id="test-live-path-disabled",
        emit_events=False,
    )

    result = evaluate_request_coupled_trace(events)

    assert events == []
    assert not result["passes_reference_gate"]


def test_generic_substrate_control_is_rejected() -> None:
    events = build_request_coupled_trace(
        sample_records(),
        run_id="test-live-path-generic",
        emit_events=True,
        scenario="generic_substrate",
    )

    result = evaluate_request_coupled_trace(events)

    assert not result["passes_reference_gate"]
    assert "pre_registered_accepted_claim" in result["gate_summary"][
        "reference_missing_requirements"
    ]
