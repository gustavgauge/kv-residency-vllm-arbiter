# Reference Offload Lifecycle Hook Evaluation

Scope: executable reference state-machine hook, not production vLLM host-offload performance.

| Scenario | Gate | Events | Bytes | Mean trace ns | Trace/s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| baseline_no_offload_hook | fail | 0 | 0 | 2653.6 | 376844.56 | 14500 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| positive_bundle_hook_disabled | fail | 0 | 0 | 18483.8 | 54101.48 | 15040 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| success_restore | fail | 6 | 5054 | 12826.5 | 77963.57 | 34509 | ordered_lifecycle_events, restoration_failure_outcome |
| failure_refusal | fail | 6 | 5182 | 12863.7 | 77738.24 | 33990 | offload_restorability, ordered_lifecycle_events |
| positive_bundle | pass | 10 | 8600 | 19277.7 | 51873.52 | 43370 | - |
| false_positive_generic_substrate | fail | 2 | 643 | 5027.6 | 198900.87 | 16480 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| false_positive_offload_no_restore | fail | 3 | 2589 | 7896.2 | 126642.67 | 22310 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_restore_after_reuse | fail | 6 | 5054 | 12465.8 | 80219.27 | 28500 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_wrong_claim_outcome | fail | 6 | 5146 | 14262.5 | 70114.14 | 28310 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_fallback_recompute | fail | 6 | 5063 | 12409.1 | 80586.32 | 28529 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |

## Overhead

| Comparison | Value |
|---|---:|
| positive_bundle_mean_ns_minus_baseline_no_hook_mean_ns | 16624.1 |
| positive_bundle_mean_ns_over_baseline_no_hook_mean_ns | 7.265 |
| positive_bundle_mean_ns_minus_event_emission_disabled_mean_ns | 793.9 |
| positive_bundle_mean_ns_over_event_emission_disabled_mean_ns | 1.043 |
| positive_bundle_events | 10 |
| positive_bundle_event_bytes | 8600 |
| positive_bundle_analyzer_runtime_ns | 43370 |
