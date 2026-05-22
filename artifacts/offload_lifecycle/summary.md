# Reference Offload Lifecycle Hook Evaluation

Scope: executable reference state-machine hook, not production vLLM host-offload performance.

| Scenario | Gate | Events | Bytes | Mean trace ns | Trace/s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| baseline_no_offload_hook | fail | 0 | 0 | 2510.4 | 398339.09 | 14670 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| positive_bundle_hook_disabled | fail | 0 | 0 | 18549.2 | 53910.6 | 14240 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| success_restore | fail | 6 | 5054 | 12505.5 | 79964.92 | 34490 | ordered_lifecycle_events, restoration_failure_outcome |
| failure_refusal | fail | 6 | 5182 | 12425.6 | 80478.8 | 33740 | offload_restorability, ordered_lifecycle_events |
| positive_bundle | pass | 10 | 8600 | 19060.3 | 52465.08 | 41270 | - |
| false_positive_generic_substrate | fail | 2 | 643 | 4940.3 | 202416.86 | 16320 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| false_positive_offload_no_restore | fail | 3 | 2589 | 7969.9 | 125472.21 | 21520 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_restore_after_reuse | fail | 6 | 5054 | 12613.6 | 79279.44 | 28770 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_wrong_claim_outcome | fail | 6 | 5146 | 13003.1 | 76904.97 | 28070 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |
| false_positive_fallback_recompute | fail | 6 | 5063 | 12555.8 | 79644.65 | 28290 | offload_restorability, ordered_lifecycle_events, restoration_failure_outcome |

## Overhead

| Comparison | Value |
|---|---:|
| positive_bundle_mean_ns_minus_baseline_no_hook_mean_ns | 16549.9 |
| positive_bundle_mean_ns_over_baseline_no_hook_mean_ns | 7.593 |
| positive_bundle_mean_ns_minus_event_emission_disabled_mean_ns | 511.1 |
| positive_bundle_mean_ns_over_event_emission_disabled_mean_ns | 1.028 |
| positive_bundle_events | 10 |
| positive_bundle_event_bytes | 8600 |
| positive_bundle_analyzer_runtime_ns | 41270 |
