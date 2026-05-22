# Live Request-Path Harness

Scope: request-path coupled reference instrumentation, not native vLLM offload.

Python: `/home/krooksn/ai/runtimes/vllm/envs/pydev-precompiled-cu130/bin/python`

vLLM: `0.21.1rc1.dev182+g9b9d5dbaa` from `/home/krooksn/ai/runtimes/vllm/repo/vllm/__init__.py`

Torch/CUDA: `2.11.0+cu130` / `13.0` on `NVIDIA GeForce RTX 3090`

| Mode | Gate | Events | Bytes | Mean latency s | Mean TTFT s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| no_hook | fail | 0 | 0 | 0.08708 | 0.066967 | 21700 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_disabled | fail | 0 | 0 | 0.08708 | 0.066967 | 13640 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_enabled | pass | 10 | 13195 | 0.08708 | 0.066967 | 46250 | - |
| false_positive_generic_substrate | fail | 2 | 1107 | 0.08708 | 0.066967 | 15790 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |

## Request Records

- `resident` request `0`: status `served`, latency `0.1738988050055923` s, TTFT `0.1098794937133789` s, prompt tokens `480`, cached tokens `0`, output tokens `8`.
- `reuse` request `1`: status `served`, latency `0.08734164098859765` s, TTFT `0.024054765701293945` s, prompt tokens `481`, cached tokens `464`, output tokens `8`.
- `failure` request `2`: status `controlled_refusal_by_harness`, latency `1.0999792721122503e-07` s, TTFT `None` s, prompt tokens `None`, cached tokens `None`, output tokens `0`.
