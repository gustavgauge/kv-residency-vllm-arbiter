# Pydev Connector Failure Semantics: fallback_recompute

Local patched pydev vLLM OffloadingConnector plus scheduler-side invalid-KV-load boundary mechanism only; not upstream ResidentClaim support, not production offload performance, and not pre-admission refusal.

Status: `ok`

Observation gate: `pass`

Failure-outcome gate: `fail`

Observation missing: `-`

Failure missing: `fail_closed_active_request_refused, no_fallback_recompute_counted_as_satisfaction, scheduler_event_before_or_at_termination, scheduler_side_active_request_refused, scheduler_side_claim_match`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.201765 | 0 | 8 | - |
| reuse | served_after_failed_load_recompute | 0.099431 | 448 | 8 | - |
