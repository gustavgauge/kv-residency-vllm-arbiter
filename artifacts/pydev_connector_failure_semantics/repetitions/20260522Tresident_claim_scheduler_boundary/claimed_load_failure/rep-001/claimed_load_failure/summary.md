# Pydev Connector Failure Semantics: claimed_load_failure

Local patched pydev vLLM OffloadingConnector plus scheduler-side invalid-KV-load boundary mechanism only; not upstream ResidentClaim support, not production offload performance, and not pre-admission refusal.

Status: `ok`

Observation gate: `fail`

Failure-outcome gate: `pass`

Observation missing: `cpu_to_gpu_restore_success`

Failure missing: `-`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| resident | served | 0.17833 | 0 | 8 | - |
| reuse | controlled_refused | 0.003132 | 0 | 0 | - |
