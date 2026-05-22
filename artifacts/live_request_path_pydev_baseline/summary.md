# Live Request-Path Harness

Scope: request-path coupled reference instrumentation, not native vLLM offload.

| Mode | Gate | Events | Bytes | Mean latency s | Mean TTFT s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| no_hook | fail | 0 | 0 | 0.102355 | 0.084188 | 21020 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_disabled | fail | 0 | 0 | 0.102355 | 0.084188 | 14880 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_enabled | pass | 10 | 13200 | 0.102355 | 0.084188 | 48560 | - |
| false_positive_generic_substrate | fail | 2 | 1107 | 0.102355 | 0.084188 | 19840 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |

## Request Records

- `resident` request `0`: status `served`, latency `0.21351695200428367` s, TTFT `0.14220905303955078` s.
- `reuse` request `1`: status `served`, latency `0.09354749199701473` s, TTFT `0.026166677474975586` s.
- `failure` request `2`: status `controlled_refusal_by_harness`, latency `8.998904377222061e-08` s, TTFT `None` s.
