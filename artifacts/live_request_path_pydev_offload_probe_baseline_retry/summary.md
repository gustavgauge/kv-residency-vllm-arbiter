# Live Request-Path Harness

Scope: request-path coupled reference instrumentation, not native vLLM offload.

Python: `/home/krooksn/ai/runtimes/vllm/envs/pydev-precompiled-cu130/bin/python`

vLLM: `0.21.1rc1.dev182+g9b9d5dbaa` from `/home/krooksn/ai/runtimes/vllm/repo/vllm/__init__.py`

Torch/CUDA: `2.11.0+cu130` / `13.0` on `NVIDIA GeForce RTX 3090`

| Mode | Gate | Events | Bytes | Mean latency s | Mean TTFT s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| no_hook | fail | 0 | 0 | 0.099658 | 0.076272 | 22980 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_disabled | fail | 0 | 0 | 0.099658 | 0.076272 | 16130 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_enabled | pass | 10 | 13197 | 0.099658 | 0.076272 | 53210 | - |
| false_positive_generic_substrate | fail | 2 | 1107 | 0.099658 | 0.076272 | 18901 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |

## Request Records

- `resident` request `0`: status `served`, latency `0.19838645699201152` s, TTFT `0.12490224838256836` s, prompt tokens `480`, cached tokens `0`, output tokens `8`.
- `reuse` request `1`: status `served`, latency `0.1005871140077943` s, TTFT `0.02764272689819336` s, prompt tokens `481`, cached tokens `464`, output tokens `8`.
- `failure` request `2`: status `controlled_refusal_by_harness`, latency `1.9000435713678598e-07` s, TTFT `None` s, prompt tokens `None`, cached tokens `None`, output tokens `0`.
