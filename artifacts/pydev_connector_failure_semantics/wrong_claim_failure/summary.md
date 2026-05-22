# Pydev Connector Failure Semantics: wrong_claim_failure

Local patched pydev vLLM OffloadingConnector mechanism only; not upstream ResidentClaim support and not production offload performance.

Status: `ok`

Observation gate: `pass`

Failure-outcome gate: `fail`

Observation missing: `-`

Failure missing: `claim_scoped_restoration_failed, controlled_cpu_to_gpu_load_failure, fail_closed_active_request_refused, scheduler_event_before_or_at_termination, scheduler_side_active_request_refused, scheduler_side_claim_match, scheduler_side_restoration_failed`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.179949 | 0 | 8 | - |
| reuse | served | 0.090816 | 448 | 8 | - |
