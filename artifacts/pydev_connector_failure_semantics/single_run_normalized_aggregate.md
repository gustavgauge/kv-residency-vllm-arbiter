# Pydev Connector Failure-Semantics Repetition Summary

Scope: local patched pydev vLLM OffloadingConnector mechanism only; not upstream vLLM support, production offload performance, or scheduler-native admission/refusal.

| Scenario | Runs | Observation pass | Failure-outcome pass | Event-sequence valid | Resident median/p95 s | Reuse median/p95 s | Event bytes median/p95 | Analyzer median/p95 ns | Failure->outcome median/p95 ns | Restore-failed->refused median/p95 ns | Outcomes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `claimed_load_failure` | 1 | 0/1 (0.000) | 1/1 (1.000) | 1/1 (1.000) | 0.173458/0.173458 | 0.002867/0.002867 | 22428/22428 | 87929/87929 | 153550/153550 | 85160/85160 | active_request_refused=1 |
| `fallback_recompute` | 1 | 1/1 (1.000) | 0/1 (0.000) | 1/1 (1.000) | 0.176843/0.176843 | 0.108364/0.108364 | 28708/28708 | 109869/109869 | - | - | fallback_recompute_not_claim_satisfaction=1 |
| `generic_counter_only` | 1 | 0/1 (0.000) | 0/1 (0.000) | 1/1 (1.000) | - | - | 378/378 | 19220/19220 | - | - | no_request_records=1 |
| `success_no_event_path` | 1 | 0/1 (0.000) | 0/1 (0.000) | 1/1 (1.000) | 0.201352/0.201352 | 0.103778/0.103778 | 0/0 | 17050/17050 | - | - | served=1 |
| `success_path` | 1 | 1/1 (1.000) | 0/1 (0.000) | 1/1 (1.000) | 0.19456/0.19456 | 0.090184/0.090184 | 17924/17924 | 68429/68429 | - | - | served=1 |
| `unclaimed_load_failure` | 1 | 0/1 (0.000) | 0/1 (0.000) | 1/1 (1.000) | 0.217786/0.217786 | 0.00297/0.00297 | 5553/5553 | 39660/39660 | - | - | not_claim_scoped=1 |
| `wrong_claim_failure` | 1 | 1/1 (1.000) | 0/1 (0.000) | 1/1 (1.000) | 0.175141/0.175141 | 0.08948/0.08948 | 18280/18280 | 69000/69000 | - | - | served=1 |
