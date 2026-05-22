# Pydev Connector Failure Semantics: success_no_event_path

Local patched pydev vLLM OffloadingConnector mechanism only; not upstream ResidentClaim support and not production offload performance.

Status: `ok`

Observation gate: `fail`

Failure-outcome gate: `fail`

Observation missing: `claim_metadata_before_lifecycle, cpu_to_gpu_restore_success, reuse_lookup_hit_requiring_load, store_offload_to_cpu_path`

Failure missing: `claim_metadata_before_lifecycle, claim_scoped_restoration_failed, controlled_cpu_to_gpu_load_failure, fail_closed_active_request_refused, restore_required_before_failure, store_offload_to_cpu_path`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.183447 | 0 | 8 | - |
| reuse | served | 0.08922 | 448 | 8 | - |
