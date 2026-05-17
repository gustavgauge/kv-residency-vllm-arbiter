# Evaluation Plan

The evaluation should prove semantic control first. Performance metrics come second.

## Core Scenario

```text
resident reusable KV = 60 blocks
active live KV       = 70 blocks
usable KV pool       = variable
block size           = 16 tokens unless runtime target differs
```

The critical boundary is 130 usable blocks.

## Policies

| Policy | Purpose |
|---|---|
| `native` | Baseline shared-pool behavior. |
| `write_no_admit` | Separates future reusable admission from active live allocation. |
| `soft_priority` | Optional comparator if vLLM target exposes usable priority semantics. |
| `hard_resident_exclude` | Protected resident blocks are not ordinary active-allocation victims. |
| `resident_reserve` | Protected resident footprint reduces active allocatable headroom. |
| `active_deferral` | Active request waits when it cannot fit under protected residents. |
| `active_refusal` | Active request receives controlled refusal when it cannot fit. |
| `offload_resident` | Optional advanced row. |
| `offload_active` | Optional advanced row. |

## Capacity Sweep

Run at least:

```text
80, 90, 100, 110, 120, 130, 150
```

Expected no-offload outcome:

| Usable blocks | Preserve 60 resident and serve 70 active? |
|---:|---|
| 80 | No |
| 90 | No |
| 100 | No |
| 110 | No |
| 120 | No |
| 130 | Yes |
| 150 | Yes |

## Required Metrics

Semantic metrics:

- active served, deferred, refused, or offloaded;
- resident claim accepted, preserved, harmed, relaxed, or offloaded;
- future reusable admission yes/no for active KV;
- protected resident blocks evicted;
- resident thresholded value;
- bulky active repeat reuse;
- claim-level value lost.

Runtime metrics:

- TTFT;
- queue delay;
- total request latency;
- tokens/sec;
- GPU KV utilization;
- free-block count;
- protected-block count;
- number of allocation retries or deferrals.

## Result Tables

The paper needs these tables from the harness:

1. Baseline/no-admit/arbiter behavior in the 60/70/80 case.
2. Capacity sweep for each policy.
3. Telemetry summary for protected resident harm.
4. Comparator boundary table for SGLang/TensorRT-LLM.

## Reviewer-Resistant Interpretation

Do not claim:

- production speedup;
- universal allocator superiority;
- that existing runtimes lack retention primitives;
- that no-admit or chunking are absent from production systems.

Do claim only if supported:

- the active/resident conflict is observable in a real runtime;
- no-admit alone does not protect residents;
- hard resident protection changes the failure mode from silent resident harm to explicit active-side action;
- the contract exposes behavior current primitive lists can obscure.
