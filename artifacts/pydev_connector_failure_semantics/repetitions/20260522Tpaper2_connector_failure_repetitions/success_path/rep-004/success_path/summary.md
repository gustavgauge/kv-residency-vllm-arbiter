# Pydev Connector Failure Semantics: success_path

Local patched pydev vLLM OffloadingConnector mechanism only; not upstream ResidentClaim support and not production offload performance.

Status: `ok`

Observation gate: `pass`

Failure-outcome gate: `fail`

Observation missing: `-`

Failure missing: `claim_scoped_restoration_failed, controlled_cpu_to_gpu_load_failure, fail_closed_active_request_refused`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.181699 | 0 | 8 | - |
| reuse | served | 0.093136 | 448 | 8 | - |
