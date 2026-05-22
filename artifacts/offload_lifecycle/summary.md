# Reference Offload Lifecycle Hook Evaluation

Scope: executable reference state-machine hook, not production vLLM host-offload performance.

| Scenario | Gate | Events | Bytes | Mean trace ns | Trace/s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| baseline_no_offload_hook | fail | 0 | 0 | 2921.1 | 342336.44 | 16850 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| positive_bundle_hook_disabled | fail | 0 | 0 | 21159.7 | 47259.68 | 16910 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| success_restore | fail | 6 | 5054 | 13748.3 | 72736.19 | 39150 | ordered_lifecycle_events, restoration_failure_outcome |
| failure_refusal | fail | 6 | 5182 | 12935.4 | 77307.14 | 33100 | offload_restorability, ordered_lifecycle_events |
| positive_bundle | pass | 10 | 8600 | 18885.8 | 52949.94 | 48370 | - |
| false_positive_generic_substrate | fail | 2 | 643 | 5073.1 | 197116.31 | 16180 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| false_positive_offload_no_restore | fail | 3 | 2589 | 8037.2 | 124421.63 | 22190 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_restore_after_reuse | fail | 6 | 5054 | 13758.8 | 72680.63 | 30730 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_wrong_claim_outcome | fail | 6 | 5146 | 14596.0 | 68511.91 | 30300 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_fallback_recompute | fail | 6 | 5063 | 14125.8 | 70792.69 | 32740 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |

## Overhead

| Comparison | Value |
|---|---:|
| positive_bundle_mean_ns_minus_baseline_no_hook_mean_ns | 15964.7 |
| positive_bundle_mean_ns_over_baseline_no_hook_mean_ns | 6.465 |
| positive_bundle_mean_ns_minus_event_emission_disabled_mean_ns | -2273.9 |
| positive_bundle_mean_ns_over_event_emission_disabled_mean_ns | 0.893 |
| positive_bundle_events | 10 |
| positive_bundle_event_bytes | 8600 |
| positive_bundle_analyzer_runtime_ns | 48370 |
