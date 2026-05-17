# Active/Resident KV Contract

This document defines the contract this repo is trying to implement inside vLLM.

## Core Boundary

```text
protected_resident_kv + active_live_kv <= usable_kv
```

If the inequality holds, active work can be served while protected resident KV remains in the usable pool.

If the inequality does not hold, the runtime must choose and report an explicit action. Silent eviction of protected resident KV is the baseline failure.

## Objects

### Resident Reusable KV

Previously computed KV that is not currently active and has predicted future value.

A resident claim must define:

- claim id;
- request or prefix id;
- logical prefix block positions;
- physical block ids when materialized;
- useful-footprint rule;
- predicted value;
- confidence;
- protection mode;
- deadline or expiry;
- allowed demotion actions.

### Active Live KV

KV needed to execute an in-flight request.

An active request must expose or estimate:

- request id;
- expected live KV blocks;
- current live KV blocks;
- chunk schedule if applicable;
- attention mode;
- urgency or deadline;
- whether active KV may be offloaded, recomputed, or made non-reusable.

### Future Reusable Admission

Whether active KV becomes reusable cached state after it is produced.

This is separate from active live allocation. A no-admit decision does not mean active KV consumed no memory while serving the request.

## Protection Modes

| Mode | Meaning |
|---|---|
| `none` | Ordinary cache behavior. |
| `soft_priority` | Resident claim influences eviction order but may still lose without explicit refusal. |
| `hard_exclude` | Protected resident blocks cannot be ordinary victims. Active work must find another action. |
| `reserve` | Resident footprint reserves capacity; active work sees reduced usable headroom. |
| `demotable` | Resident claim can be offloaded or relaxed with telemetry. |

## Required Arbiter Actions

The prototype does not need to implement every action first. It must name the action it takes.

| Action | Meaning |
|---|---|
| `serve_active_preserve_resident` | Feasible; active runs and residents survive. |
| `serve_active_evict_resident` | Active runs by harming resident claims. Baseline behavior. |
| `serve_active_no_admit` | Active runs but its produced KV is not future reusable. |
| `defer_active` | Active request waits for headroom. |
| `refuse_active` | Active request cannot be served under current resident claims. |
| `offload_resident` | Resident state moves to slower memory. |
| `offload_active` | Active state uses slower memory or another pool. |
| `bound_active_live` | Runtime frees, recomputes, or limits active live KV. |
| `route_elsewhere` | Active request moves to another worker. |
| `relax_resident_claim` | Resident claim is downgraded or partially evicted. |
| `capacity_required` | No local action is available without more memory. |

## Minimal Prototype Contract

The first vLLM prototype only needs:

1. resident claim metadata;
2. hard resident victim exclusion or reserve;
3. active defer/refuse when active live KV cannot fit;
4. write no-admit as a separate future-admission knob;
5. telemetry for accepted, refused, evicted, and harmed claims.

This is enough to prove the semantic split.
