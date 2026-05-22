# Pydev Connector Failure Semantics: unclaimed_load_failure

Local patched pydev vLLM OffloadingConnector plus scheduler-side invalid-KV-load boundary mechanism only; not upstream ResidentClaim support, not production offload performance, and not pre-admission refusal.

Status: `ok`

Observation gate: `fail`

Failure-outcome gate: `fail`

Observation missing: `claim_metadata_before_lifecycle, cpu_to_gpu_restore_success, reuse_lookup_hit_requiring_load, store_offload_to_cpu_path`

Failure missing: `claim_metadata_before_lifecycle, claim_scoped_restoration_failed, controlled_cpu_to_gpu_load_failure, fail_closed_active_request_refused, restore_required_before_failure, scheduler_event_before_or_at_termination, scheduler_side_active_request_refused, scheduler_side_claim_match, scheduler_side_restoration_failed, store_offload_to_cpu_path`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.178232 | 0 | 8 | - |
| reuse | generic_connector_load_failed | 0.002697 | 0 | 0 | - |
