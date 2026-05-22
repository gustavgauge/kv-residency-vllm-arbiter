# Pydev Connector Failure Semantics: claimed_load_failure

Local patched pydev vLLM OffloadingConnector mechanism only; not upstream ResidentClaim support and not production offload performance.

Status: `ok`

Observation gate: `fail`

Failure-outcome gate: `pass`

Observation missing: `cpu_to_gpu_restore_success`

Failure missing: `-`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.19998 | 0 | 8 | - |
| reuse | controlled_refused | 0.003155 | 0 | 0 | - |
