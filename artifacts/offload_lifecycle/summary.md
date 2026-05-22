# Reference Offload Lifecycle Hook Evaluation

Scope: executable reference state-machine hook, not production vLLM host-offload performance.

| Scenario | Gate | Events | Bytes | Mean trace ns | Trace/s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| baseline_no_offload_hook | fail | 0 | 0 | 2569.1 | 389240.76 | 14250 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| positive_bundle_hook_disabled | fail | 0 | 0 | 18410.3 | 54317.5 | 14310 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| success_restore | fail | 6 | 5054 | 12478.8 | 80135.87 | 34510 | ordered_lifecycle_events, restoration_failure_outcome |
| failure_refusal | fail | 6 | 5182 | 12423.8 | 80490.5 | 33190 | offload_restorability, ordered_lifecycle_events |
| positive_bundle | pass | 10 | 8600 | 18814.4 | 53150.91 | 41650 | - |
| false_positive_generic_substrate | fail | 2 | 643 | 5104.4 | 195908.41 | 16590 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| false_positive_offload_no_restore | fail | 3 | 2589 | 7911.5 | 126398.6 | 21420 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_restore_after_reuse | fail | 6 | 5054 | 12324.2 | 81141.33 | 28230 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_wrong_claim_outcome | fail | 6 | 5146 | 12804.1 | 78100.07 | 27260 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_fallback_recompute | fail | 6 | 5063 | 12453.5 | 80298.41 | 27210 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |

## Overhead

| Comparison | Value |
|---|---:|
| positive_bundle_mean_ns_minus_baseline_no_hook_mean_ns | 16245.3 |
| positive_bundle_mean_ns_over_baseline_no_hook_mean_ns | 7.323 |
| positive_bundle_mean_ns_minus_event_emission_disabled_mean_ns | 404.1 |
| positive_bundle_mean_ns_over_event_emission_disabled_mean_ns | 1.022 |
| positive_bundle_events | 10 |
| positive_bundle_event_bytes | 8600 |
| positive_bundle_analyzer_runtime_ns | 41650 |
