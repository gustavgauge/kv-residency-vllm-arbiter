# Live vLLM Request-Path Gate

Scope: this gate is for request-path coupled evidence. It must not be read as
native upstream vLLM ResidentClaim support unless the events are emitted by the
runtime hook points named below and not by the reference harness alone.

## Passing Trace

The live request path may pass only when an ordered trace carries live request
ids and the following contract events:

| Order | Contract event | Existing reference event |
|---:|---|---|
| 1 | `claim_accepted` | `resident_claim_accepted` |
| 2 | `predicate_materialized` | `resident_claim_materialized` |
| 3 | `claim_offloaded` | `resident_claim_offloaded` |
| 4 | `restore_required_for_reuse` | `resident_claim_restore_required` |
| 5 | `claim_restored_before_reuse` | `resident_claim_restored` |
| 6 | `reuse_consumed_restored_state` | `resident_claim_reuse_after_restore` |
| 7 | `restoration_unavailable_injected` | `resident_claim_restoration_failed` with `controlled_restoration_unavailable=true` |
| 8 | `restoration_failed(claim_id)` | `resident_claim_restoration_failed` with matching `outcome_claim_id` |
| 9 | `active_request_refused(blocking_claim_id = claim_id)` | `active_request_refused` |

Every semantic event must carry claim id, predicate id or materialization
predicate, reusable-object or prefix identity, request id, cache identity,
token-map identity, block ids or block-count footprint, tier/source/destination
where applicable, event sequence or monotonic timestamp, offload/restoration
generation, and failure outcome claim id.

## False-Positive Controls

The live gate must fail:

| Control | Required rejection reason |
|---|---|
| Generic transfer/offload/onboard counters only | No accepted claim, predicate, token-map, cache, or outcome identity. |
| Restore after reuse | Restoration is not ordered before predicate-satisfying reuse. |
| Fallback recompute as restore | Restoration did not come from the offload tier. |
| Wrong-claim restoration failure | Failure outcome is not scoped to the accepted claim id. |
| Post-hoc claim naming | Claim was not accepted before lifecycle transitions. |
| Missing anchors | Claim, predicate, token-map, cache, reusable object, or block footprint is absent. |
| Missing ordering | Event sequence cannot reconstruct acceptance -> materialization -> offload -> restore/reuse -> failure/outcome. |
| Missing predicate/cache/token-map identity | The trace cannot distinguish resident claim state from substrate counters. |

## Hook Points Inspected

| Lane | Hook points | Feasibility |
|---|---|---|
| vLLM 0.19.1 patched prototype | `vllm/v1/core/block_pool.py`, `vllm/v1/core/kv_cache_manager.py`, `vllm/v1/core/sched/scheduler.py`, and `vllm/v1/core/kv_residency_telemetry.py` from `patches/vllm_resident_claim_prototype.patch` | Narrowest existing request-serving lane for accepted claim, materialization, and active refusal. No native offload lifecycle in the archived prototype. |
| vLLM 0.21.0 / current main offload connector | `vllm/distributed/kv_transfer/kv_connector/v1/offloading/scheduler.py`, `vllm/distributed/kv_transfer/kv_connector/v1/offloading/worker.py`, `vllm/v1/kv_offload/worker/worker.py`, `vllm/v1/kv_offload/base.py`, and `vllm/v1/request.py` | Stronger native substrate for lookup, load, store, completion, and per-request `kv_transfer_params`. Porting claim acceptance and outcome semantics here is real integration work. |

## Current Harness

`scripts/run_live_request_path_harness.py` is deliberately a bridge, not a
native vLLM patch. When vLLM is importable, it runs resident and reuse requests
through `vllm.LLM.generate`, records request ids and timing, and drives the
reference lifecycle/outcome hook with those live ids. The failure leg is a
controlled harness refusal. The output therefore supports only this claim:

```text
request-path coupled reference instrumentation can satisfy the lifecycle gate
when supplied live vLLM request ids/timing.
```

It does not show native vLLM host offload, production serving overhead, or
upstream ResidentClaim support.
