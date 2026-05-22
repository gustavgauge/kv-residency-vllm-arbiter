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

## 2026-05-22 Live Runtime Result

The previous `blocked_missing_vllm_runtime` result came from selecting
`/usr/bin/python3`, which lacks `torch` and `vllm`. It is an environment
selection failure, not evidence that the workstation lacks a runnable vLLM
runtime.

Using the configured audit Python recorded in the historical summary metadata,
the harness ran vLLM 0.21.0 with `HuggingFaceTB/SmolLM2-135M-Instruct`,
`max_model_len=512`, `max_tokens=8`, and `gpu_memory_utilization=0.35`. The
resident request produced request id `0`, 480 prompt tokens, 8 output tokens, 0
cached tokens, 0.198272 s wall latency, and 0.124332 s TTFT. The reuse request
produced request id `1`, 481 prompt tokens, 8 output tokens, 464 cached tokens,
0.100546 s wall latency, and 0.027612 s TTFT.

The reference-emission mode passed the lifecycle/outcome gate with 10 events,
13,203 bytes, 52,370 ns analyzer runtime, active claim count 1, and registry
size 1. The baseline no-hook and event-emission-disabled modes both failed the
gate with zero events. The generic substrate false-positive control failed the
gate with two generic events. This is useful request-path evidence, but it is
still `request_path_coupled_reference_not_native_vllm_offload`.

The editable pydev lane was also exercised after adding an env-gated Python-side
probe. With `VLLM_RESIDENT_CLAIM_EVENT_PATH` set and ResidentClaim-shaped
`kv_transfer_params` injected, the patched vLLM request hook emitted two
runtime JSONL records, one per served request, under
`artifacts/live_request_path_pydev_hook_enabled/vllm_runtime_events.jsonl`.
Those events use vLLM internal request ids with suffixes, while the harness
summary records the public `RequestOutput` ids. They are joinable by role,
claim id, and prompt digest, not evidence of a native offload lifecycle. The
events came from `Request` construction, not from the native offload connector.
vLLM warned that no KVConnector was configured and disabled KVTransfer for those
requests, so native offload support is still not claimed.

## 2026-05-22 Pydev OffloadingConnector Probe

The editable pydev lane can activate vLLM's Python-side
`OffloadingConnector` in-process by passing `kv_transfer_config` to `LLM(...)`:

```json
{
  "kv_connector": "OffloadingConnector",
  "kv_role": "kv_both",
  "kv_connector_extra_config": {
    "block_size": 64,
    "cpu_bytes_to_use": 536870912,
    "store_threshold": 1
  }
}
```

Using `HuggingFaceTB/SmolLM2-135M-Instruct`, `max_model_len=512`,
`max_tokens=8`, `enable_prefix_caching=True`, `enforce_eager=True`,
`disable_log_stats=True`, and `VLLM_ENABLE_V1_MULTIPROCESSING=0`, the probe
served a resident request, reset only the local prefix cache
(`reset_connector=false`), and served a reuse request. The final run is under
`artifacts/live_request_path_pydev_offload_connector_inprocess_joined/`.

The final event stream contains 14 patched-runtime events:

| Event | Count | Claim-joined |
|---|---:|---:|
| `request_initialized` | 2 | 2 |
| `offload_lookup_result` | 2 | 2 |
| `offload_store_job_created` | 1 | 1 |
| `offload_load_job_created` | 1 | 1 |
| `offload_worker_transfer_submitted` | 2 | 2 |
| `offload_worker_transfer_finished` | 2 | 2 |
| `offload_job_completed` | 2 | 2 |
| `offload_request_finished_no_pending_jobs` | 2 | 2 |

The resident request stored 7 offload blocks (`GPU -> CPU` worker transfer).
After the local prefix-cache reset, the reuse request observed 448 external hit
tokens, created one load job, and completed a `CPU -> GPU` worker transfer
before request finish. Worker submit/finish events are joined through an
env-gated job-id registry in the local pydev telemetry helper.

This is stronger than request-path-coupled reference evidence: it shows that
vLLM's real offload connector path can carry claim-scoped lifecycle
observations in a patched pydev in-process run. It is still not ResidentClaim
`offloadable` conformance. The run does not show runtime claim acceptance,
predicate enforcement, restoration failure injection, claim-scoped refusal, or
expiry/demotion/harm semantics.

One route-specific issue remains: with `disable_log_stats=False`, the first
connector run emitted a store and worker completion, then failed in vLLM's
`OffloadingConnector` metrics observer with an `AssertionError` while processing
transfer stats. The successful connector evidence therefore disables stats
logging and records latency/request counters from the harness summary rather
than vLLM stat logging. The bounded follow-up inspection found an existing
vLLM OffloadingConnector stats serialization mismatch: `record_transfer()`
stores `OffloadingOperationMetrics` objects, while `reduce()` and the
Prometheus observer assert dict-shaped operations. This is treated as a threat
to validity for vLLM stats/TTFT, not as a ResidentClaim mechanism failure.

## 2026-05-22 Pydev Connector Failure Semantics

`scripts/run_pydev_connector_failure_semantics.py` exercises the same patched
pydev `OffloadingConnector` path with an env-gated CPU-to-GPU load failure. The
scenario artifacts are under
`artifacts/pydev_connector_failure_semantics/`, and
`kv_vllm_arbiter.pydev_connector_failure.evaluate_pydev_connector_events`
classifies the event streams.

The passing failure scenario is `claimed_load_failure`. It first stores resident
KV through a `GPU -> CPU` worker transfer, resets only the local prefix cache,
observes a reuse lookup hit for 448 tokens, creates a load job, injects a
controlled failure into that same claim's `CPU -> GPU` worker transfer, and then
emits scheduler-side boundary events before the request-finished hook, followed
by the existing connector-level outcome:

| Ordered event | Required boundary |
|---|---|
| `resident_claim_restore_required` | Same claim id, request id, predicate, prefix/reusable object, cache identity, token-map identity, job id, transfer type, and synthesized restoration generation. |
| `offload_worker_transfer_finished` | `CPU -> GPU`, `success=false`, controlled failure reason, and same claim/job. |
| `scheduler_resident_claim_restoration_failed` | Scheduler observed the invalid-KV-load branch, same claim id, request id, invalid block ids/count, failure policy, and `finish_status=FINISHED_ERROR`. |
| `scheduler_active_request_refused` | Same claim id in `blocking_claim_ids`, `scheduler_side_refusal=true`, and `native_scheduler_admission_refusal=false`. |
| `offload_request_finished_pending_jobs` | Request termination boundary; scheduler-side events must occur before or at this boundary. |
| `offload_load_job_failed` | Existing connector failed-load propagation with same claim/job and load direction. |
| `resident_claim_restoration_failed` | Existing connector-level `outcome_claim_id` equals the accepted claim id. |
| `active_request_refused` | Existing connector-level `blocking_claim_ids` contains that claim id. |

The strengthened refusal is a controlled patched scheduler-boundary outcome at
vLLM's existing invalid-KV-load handling branch. It is not native/upstream vLLM
support and not pre-admission refusal: restoration failure is discovered during
CPU-to-GPU restoration. The result supports only this claim:

```text
local patched vLLM connector mechanism, with scheduler-side invalid-KV-load
boundary telemetry, satisfies the offload lifecycle/outcome gate under
controlled failure injection.
```

The controls intentionally fail the outcome gate:

| Control | Gate behavior |
|---|---|
| `success_path` | Passes connector observation, fails failure outcome because restore succeeds. |
| `wrong_claim_failure` | Fails failure outcome because the injected claim id does not match the accepted claim. |
| `unclaimed_load_failure` | Fails failure outcome and emits no claim-scoped ResidentClaim refusal. |
| `ordinary_offload_no_claim` | Performs ordinary connector store/load activity but fails observation and failure gates because no ResidentClaim metadata is present. |
| `generic_counter_only` | Fails because generic counters lack claim, predicate, cache, token-map, and outcome identity. |
| `fallback_recompute` | Fails because request service after a failed load is not counted as satisfying the accepted claim without prior refusal/demotion/expiry/harm. |

The checked-in repeated scheduler-boundary run is
`artifacts/pydev_connector_failure_semantics/repetitions/20260522Tresident_claim_scheduler_boundary/`.
New public reruns should use similarly neutral run-set ids, for example:

```bash
export VLLM_AUDIT_PYTHON=/path/to/python-with-patched-vllm
export VLLM_KV_RESIDENCY_VLLM_SOURCE=/path/to/vllm-checkout
python3 scripts/run_pydev_connector_failure_repetitions.py \
  --run-set-id 20260522Tresident_claim_scheduler_boundary
```

`scripts/normalize_pydev_connector_failure_semantics.py` and the repetition
harness write `normalized_summary.json` next to raw scenario summaries and
aggregate rows in `aggregate.json`, `aggregate.md`, and
`normalized_summaries.jsonl`. The repeated aggregate records:

| Scenario | Runs | Observation pass | Failure-outcome pass | Event-sequence valid |
|---|---:|---:|---:|---:|
| `success_no_event_path` | 30 | 0/30 | 0/30 | 30/30 |
| `success_path` | 30 | 30/30 | 0/30 | 30/30 |
| `ordinary_offload_no_claim` | 10 | 0/10 | 0/10 | 10/10 |
| `claimed_load_failure` | 30 | 0/30 | 30/30 | 30/30 |
| `wrong_claim_failure` | 10 | 10/10 | 0/10 | 10/10 |
| `unclaimed_load_failure` | 10 | 0/10 | 0/10 | 10/10 |
| `fallback_recompute` | 10 | 10/10 | 0/10 | 10/10 |
| `generic_counter_only` | 1 | 0/1 | 0/1 | 1/1 |

For the 30 `claimed_load_failure` repetitions, all 30 normalized rows record
`scheduler_side_failure_outcome_present=true`,
`scheduler_side_refusal_present=true`, `scheduler_side_claim_match=true`,
`scheduler_event_before_or_at_termination=true`,
`connector_level_outcome_present=true`, and
`native_scheduler_admission_refusal=false`.
