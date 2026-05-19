# vLLM Prototype Patch Notes

Target branch:

```text
resident-kv-claims-vllm-prototype
```

Base commit:

```text
b1388b1fbf5aaef47937fabe98931211684666a6
```

This repository holds the artifact harnesses. The vLLM branch holds the runtime
patch. Use `VLLM_AUDIT_PYTHON` to choose the Python environment that imports the
patched runtime.

## Files Changed In vLLM

| File | Purpose |
|---|---|
| `vllm/v1/core/kv_residency_telemetry.py` | Env-gated JSONL writer for active/resident KV traces. |
| `vllm/v1/core/kv_cache_manager.py` | Emits active admission/defer/refusal and future-reuse admission events. |
| `vllm/v1/core/block_pool.py` | Emits resident materialization, allocation-victim, claim lifecycle, and hard-exclusion telemetry. |
| `vllm/v1/core/sched/scheduler.py` | Turns protected-resident scheduler pressure into bounded active refusal. |
| `vllm/v1/core/single_type_kv_cache_manager.py` | Passes request ids into block allocation calls for telemetry attribution. |

The incremental patch `vllm_runtime_metadata_joinability.patch` also touches:

| File | Purpose |
|---|---|
| `vllm/entrypoints/openai/chat_completion/serving.py` | Emits opt-in request-joinable runtime metadata JSONL for chat completions. |
| `vllm/v1/core/kv_residency_telemetry.py` | Adds `proxy_request_id`/`runtime_request_id` to arbiter telemetry, normalizes vLLM's internal request suffix, and adds a runtime metadata sidecar writer. |

## Behavior Boundary

The prototype demonstrates runtime semantics, not a production policy. It adds:

- native allocation telemetry for the 60 resident / 70 active / 80 usable case;
- write no-admit as a separate future-reuse admission control;
- resident claim metadata with useful leading-prefix thresholds;
- leading-prefix predicate evaluation over logical block positions, not raw
  surviving block count;
- hard resident exclusion from ordinary free-block victims;
- active refusal/defer attribution to blocking resident claims;
- demotion and expiry events before later block loss;
- scheduler-path evidence through `vllm.LLM.generate`.

It does not claim production throughput, optimized scheduling, learned
prediction, fairness, or upstream API stability.

## Main Evidence Commands

```bash
make native-blockpool-probe
make no-admit-probe
make claim-metadata-probe
make hard-claim-probe
make capacity-sweep
make claim-lifecycle
make conformance
make live-scheduler-pressure
```

The hard-claim pressure trace should show an accepted resident claim,
materialized useful-prefix predicate, active infeasibility, and either active
refusal/defer or a prior claim release event. Loss after explicit demotion or
expiry is reported as post-release block loss, not claim harm.

## Runtime Metadata Joinability

`vllm_runtime_metadata_joinability.patch` adds opt-in JSONL metadata for live
OpenAI-compatible chat completions. Enable it with
`VLLM_KV_RESIDENCY_RUNTIME_METADATA_PATH`. The patch also extends existing
arbiter telemetry with join keys:

- `proxy_request_id`
- `runtime_request_id`
- `event_type`
- `event_time`
- `runtime_name`
- `runtime_commit`

For OpenAI serving, caller-provided `request_id` becomes the proxy/runtime join
key. Lower scheduler events may append an internal 8-hex suffix to the runtime
request id; the telemetry helper strips that suffix when writing
`proxy_request_id` so allocator events remain joinable to proxy traces.

## Capacity Telemetry Correction

`vllm_pressure_capacity_telemetry.patch` is a narrow follow-on telemetry patch.
It stops the JSONL writer from inventing `usable_blocks=0` when no capacity
snapshot is available, adds actual allocatable `usable_blocks` to
`BlockPool.kv_residency_conflict_fields`, and includes the same pressure
snapshot on `active_request_admitted` rows. This is telemetry only; it does not
change the admission/refusal policy.
