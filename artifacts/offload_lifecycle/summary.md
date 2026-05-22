# Reference Offload Lifecycle Hook Evaluation

Scope: executable reference state-machine hook, not production vLLM host-offload performance.

| Scenario | Gate | Events | Bytes | Mean trace ns | Trace/s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| baseline_no_offload_hook | fail | 0 | 0 | 2585.3 | 386807.54 | 14509 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| positive_bundle_hook_disabled | fail | 0 | 0 | 18585.6 | 53805.04 | 14340 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| success_restore | fail | 6 | 5054 | 12344.3 | 81009.3 | 33950 | ordered_lifecycle_events, restoration_failure_outcome |
| failure_refusal | fail | 6 | 5182 | 12324.5 | 81139.05 | 32929 | offload_restorability, ordered_lifecycle_events |
| positive_bundle | pass | 10 | 8600 | 18803.4 | 53181.74 | 40630 | - |
| false_positive_generic_substrate | fail | 2 | 643 | 5089.2 | 196494.85 | 16080 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| false_positive_offload_no_restore | fail | 3 | 2589 | 8001.8 | 124971.16 | 21499 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_restore_after_reuse | fail | 6 | 5054 | 12362.2 | 80891.87 | 27840 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_wrong_claim_outcome | fail | 6 | 5146 | 13092.0 | 76382.3 | 27520 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_fallback_recompute | fail | 6 | 5063 | 12515.6 | 79900.14 | 28120 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |

## Overhead

| Comparison | Value |
|---|---:|
| positive_bundle_mean_ns_minus_baseline_no_hook_mean_ns | 16218.1 |
| positive_bundle_mean_ns_over_baseline_no_hook_mean_ns | 7.273 |
| positive_bundle_mean_ns_minus_event_emission_disabled_mean_ns | 217.8 |
| positive_bundle_mean_ns_over_event_emission_disabled_mean_ns | 1.012 |
| positive_bundle_events | 10 |
| positive_bundle_event_bytes | 8600 |
| positive_bundle_analyzer_runtime_ns | 40630 |
