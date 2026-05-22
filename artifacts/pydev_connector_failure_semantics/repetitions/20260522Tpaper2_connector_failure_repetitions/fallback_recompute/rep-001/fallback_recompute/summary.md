# Pydev Connector Failure Semantics: fallback_recompute

Local patched pydev vLLM OffloadingConnector mechanism only; not upstream ResidentClaim support and not production offload performance.

Status: `ok`

Observation gate: `pass`

Failure-outcome gate: `fail`

Observation missing: `-`

Failure missing: `fail_closed_active_request_refused, fallback_recompute_counted_as_satisfaction`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.201819 | 0 | 8 | - |
| reuse | served_after_failed_load_recompute | 0.104901 | 448 | 8 | - |
