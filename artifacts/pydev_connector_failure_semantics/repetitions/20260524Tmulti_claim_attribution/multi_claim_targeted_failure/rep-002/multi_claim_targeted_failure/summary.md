# Pydev Connector Failure Semantics: multi_claim_targeted_failure

Local patched pydev vLLM OffloadingConnector plus scheduler-side invalid-KV-load boundary mechanism only; not upstream ResidentClaim support, not production offload performance, and not pre-admission refusal.

Status: `ok`

Observation gate: `fail`

Failure-outcome gate: `pass`

Observation missing: `cpu_to_gpu_restore_success`

Failure missing: `-`

| Role | Status | Latency s | Cached tokens | Output tokens | Exception |
|---|---|---:|---:|---:|---|
| control_resident | served | 0.176694 | 0 | 8 | - |
| control_reuse | served | 0.089147 | 448 | 8 | - |
| target_resident | served | 0.087323 | 0 | 8 | - |
| target_reuse | controlled_refused | 0.00272 | 0 | 0 | - |

Multi-claim attribution gate: `pass`

Multi-claim missing: `-`
