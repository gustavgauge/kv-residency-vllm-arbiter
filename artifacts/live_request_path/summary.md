# Live Request-Path Harness

Scope: request-path coupled reference instrumentation, not native vLLM offload.

Python: `/home/krooksn/ai/runtimes/vllm/envs/stable-wheel-auto/bin/python`

vLLM: `0.21.0` from `/home/krooksn/ai/runtimes/vllm/envs/stable-wheel-auto/lib/python3.12/site-packages/vllm/__init__.py`

Torch/CUDA: `2.11.0+cu130` / `13.0` on `NVIDIA GeForce RTX 3090`

| Mode | Gate | Events | Bytes | Mean latency s | Mean TTFT s | Analyzer ns | Missing requirements |
|---|---|---:|---:|---:|---:|---:|---|
| no_hook | fail | 0 | 0 | 0.099606 | 0.075972 | 22100 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_disabled | fail | 0 | 0 | 0.099606 | 0.075972 | 15870 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |
| hook_integrated_event_emission_enabled | pass | 10 | 13203 | 0.099606 | 0.075972 | 52370 | - |
| false_positive_generic_substrate | fail | 2 | 1107 | 0.099606 | 0.075972 | 23180 | fixed_cache_identity_and_deterministic_request_token_map, materialization_predicate, offload_restorability, ordered_lifecycle_events, pre_registered_accepted_claim, restoration_failure_outcome, reusable_object_id, stable_claim_id_and_fixed_materialization_predicate |

## Request Records

- `resident` request `0`: status `served`, latency `0.19827240098675247` s, TTFT `0.12433195114135742` s, prompt tokens `480`, cached tokens `0`, output tokens `8`.
- `reuse` request `1`: status `served`, latency `0.10054570299689658` s, TTFT `0.027611970901489258` s, prompt tokens `481`, cached tokens `464`, output tokens `8`.
- `failure` request `2`: status `controlled_refusal_by_harness`, latency `2.1999585442245007e-07` s, TTFT `None` s, prompt tokens `None`, cached tokens `None`, output tokens `0`.
