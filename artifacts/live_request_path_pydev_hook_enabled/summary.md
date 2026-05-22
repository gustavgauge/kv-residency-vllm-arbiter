# Live Request-Path Harness

Scope: request-path coupled reference instrumentation, not native vLLM offload.

Python: `/home/krooksn/ai/runtimes/vllm/envs/pydev-precompiled-cu130/bin/python`

vLLM: `0.21.1rc1.dev182+g9b9d5dbaa` from `/home/krooksn/ai/runtimes/vllm/repo/vllm/__init__.py`

Torch/CUDA: `2.11.0+cu130` / `13.0` on `NVIDIA GeForce RTX 3090`

| Mode | Gate | Events | Bytes | Mean latency s | Mean TTFT s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| no_hook | fail | 0 | 0 | 0.09748 | 0.075761 | 20570 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_disabled | fail | 0 | 0 | 0.09748 | 0.075761 | 14650 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_enabled | pass | 10 | 13199 | 0.09748 | 0.075761 | 47930 | - |
| false_positive_generic_substrate | fail | 2 | 1107 | 0.09748 | 0.075761 | 16930 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |

## Request Records

- `resident` request `0`: status `served`, latency `0.1976831820065854` s, TTFT `0.12485814094543457` s, prompt tokens `480`, cached tokens `0`, output tokens `8`.
- `reuse` request `1`: status `served`, latency `0.09475659500458278` s, TTFT `0.026664018630981445` s, prompt tokens `481`, cached tokens `464`, output tokens `8`.
- `failure` request `2`: status `controlled_refusal_by_harness`, latency `1.8998980522155762e-07` s, TTFT `None` s, prompt tokens `None`, cached tokens `None`, output tokens `0`.
