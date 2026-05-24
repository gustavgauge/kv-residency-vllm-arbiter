# Pydev Connector Failure-Semantics Repetition Summary

Scope: local patched pydev vLLM OffloadingConnector mechanism with scheduler-side invalid-KV-load boundary evidence; not upstream vLLM support, production offload performance, or scheduler-native pre-admission refusal.

| Scenario | Runs | Observation pass | Failure-outcome pass | Event-sequence valid | Resident median/p95 s | Reuse median/p95 s | Event bytes median/p95 | Analyzer median/p95 ns | Failure->outcome median/p95 ns | Restore-failed->refused median/p95 ns | Outcomes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `multi_claim_targeted_failure` | 3 | 0/3 (0.000) | 3/3 (1.000) | 3/3 (1.000) | - | - | 46619/46620 | 168610/171470 | 143790/144809 | 74560/74760 | active_request_refused=3 |
